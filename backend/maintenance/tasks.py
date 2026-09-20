"""정비 이력 업로드 처리 (specs/10 §2~3)."""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from common.jobs import report_progress
from ingestion.models import BatchStatus, UploadBatch
from maintenance.models import FoulingKeyword, MaintenanceRecord, ReviewStatus
from maintenance.services import extractor, parser
from units.settings_resolver import get_setting

logger = logging.getLogger(__name__)


def active_keywords() -> list[extractor.Keyword]:
    return [
        extractor.Keyword(keyword=row.keyword, category=row.category, weight=row.weight)
        for row in FoulingKeyword.objects.filter(is_active=True)
    ]


def apply_extraction(record: MaintenanceRecord, keywords, threshold: float) -> None:
    result = extractor.match(record.title, record.description, keywords, threshold)
    record.is_fouling_related = result.is_fouling_related
    record.matched_keywords = result.matched
    record.match_score = result.score
    record.match_category = result.category


@shared_task(bind=True, name="maintenance.import_records")
def import_maintenance(
    self, batch_id: int, sheet: str | None = None, mapping: dict | None = None
) -> dict:
    """파일을 파싱해 MaintenanceRecord 로 적재하고 키워드 추출을 돌린다.

    **추출 결과는 후보일 뿐이다.** 승인 전에는 CleaningEvent 로 등록되지 않는다(AC-10-2).
    """
    batch = UploadBatch.objects.select_related("unit").get(pk=batch_id)

    try:
        report_progress(self, 10, "파일 읽기")
        result = parser.parse(batch.stored_path, sheet=sheet, mapping=mapping)

        report = {
            "row_total": len(result.rows),
            "header": result.header,
            "mapping": result.mapping,
            "sheets": result.sheets,
            "errors": result.errors,
            "warnings": result.warnings,
            "is_loadable": result.is_ok,
        }

        if not result.is_ok:
            batch.validation_report = report
            batch.status = BatchStatus.FAILED
            batch.save(update_fields=["validation_report", "status"])
            return report

        report_progress(self, 50, "키워드 추출")
        keywords = active_keywords()
        threshold = float(get_setting("extraction_threshold", batch.unit_id))

        objects = []
        for row in result.rows:
            record = MaintenanceRecord(
                unit=batch.unit,
                upload_batch=batch,
                work_date=row["work_date"],
                work_type=row["work_type"],
                title=row["title"],
                description=row["description"],
                cost=row["cost"],
                duration_days=row["duration_days"],
                worker=row["worker"],
                review_status=ReviewStatus.PENDING,
            )
            apply_extraction(record, keywords, threshold)
            objects.append(record)

        with transaction.atomic():
            MaintenanceRecord.objects.filter(upload_batch=batch).delete()
            MaintenanceRecord.objects.bulk_create(objects, batch_size=1000)

            candidates = sum(1 for o in objects if o.is_fouling_related)
            report.update(
                {
                    "row_loaded": len(objects),
                    "fouling_candidates": candidates,
                    "cleaning_candidates": sum(
                        1 for o in objects if o.match_category == extractor.CATEGORY_CLEANING
                    ),
                }
            )
            batch.validation_report = report
            batch.row_total = len(objects)
            batch.row_loaded = len(objects)
            batch.status = BatchStatus.LOADED
            batch.save(update_fields=["validation_report", "row_total", "row_loaded", "status"])

        report_progress(self, 100, "완료")
        logger.info("maintenance imported batch_id=%s rows=%s", batch_id, len(objects))
        return report

    except Exception as exc:  # noqa: BLE001
        logger.exception("maintenance import failed batch_id=%s", batch_id)
        batch.status = BatchStatus.FAILED
        batch.error_message = str(exc)[:2000]
        batch.save(update_fields=["status", "error_message"])
        raise


@shared_task(bind=True, name="maintenance.re_extract")
def re_extract(self, unit_id: int | None = None) -> dict:
    """키워드 사전 변경 후 재추출 (specs/15 §7).

    이미 승인·무시 처리된 레코드는 건드리지 않는다.
    """
    keywords = active_keywords()
    threshold = float(get_setting("extraction_threshold", unit_id))

    queryset = MaintenanceRecord.objects.filter(review_status=ReviewStatus.PENDING)
    if unit_id:
        queryset = queryset.filter(unit_id=unit_id)

    records = list(queryset)
    for record in records:
        apply_extraction(record, keywords, threshold)
    MaintenanceRecord.objects.bulk_update(
        records,
        ["is_fouling_related", "matched_keywords", "match_score", "match_category"],
        batch_size=1000,
    )
    return {
        "updated": len(records),
        "candidates": sum(1 for r in records if r.is_fouling_related),
    }
