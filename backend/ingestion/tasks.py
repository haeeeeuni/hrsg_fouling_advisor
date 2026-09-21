"""업로드 검증·적재 Celery 태스크 (specs/03 §2, §5).

얇은 조립층이다. 실제 판정 로직은 ingestion/services/* 의 순수 함수가 담당한다.
"""

from __future__ import annotations

import logging

import pandas as pd
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from common.jobs import report_progress
from ingestion.models import BatchStatus, DuplicatePolicy, Measurement, UploadBatch
from ingestion.services import reader
from ingestion.services.transform import mapping_specs_from_rows
from ingestion.services.validator import ValueValidator, validate_structure
from units.settings_resolver import get_setting
from units.standard_fields import ALL_FIELD_KEYS, TIMESTAMP, resolve_ranges

logger = logging.getLogger(__name__)

BULK_BATCH_SIZE = 5000
MEASUREMENT_FIELDS = [key for key in ALL_FIELD_KEYS if key != TIMESTAMP]


def _mapping_rows(unit) -> list[dict]:
    return list(
        unit.column_mappings.values(
            "standard_field",
            "source_column",
            "scale_factor",
            "offset",
            "bool_rule",
            "bool_threshold",
        )
    )


@shared_task(bind=True, name="ingestion.validate_upload")
def validate_upload(self, batch_id: int) -> dict:
    """파일을 훑어 검증 리포트를 만든다. **DB에 Measurement 를 쓰지 않는다.**"""
    batch = UploadBatch.objects.select_related("unit").get(pk=batch_id)
    unit = batch.unit

    try:
        report_progress(self, 5, "파일 읽기")
        encoding = reader.detect_encoding(batch.stored_path)
        delimiter = reader.detect_delimiter(batch.stored_path, encoding)
        header = reader.read_header(batch.stored_path, encoding, delimiter)
        duplicates = reader.find_duplicate_headers(header)

        specs = mapping_specs_from_rows(_mapping_rows(unit))
        ranges = resolve_ranges(get_setting("physical_ranges", unit.id), unit.rated_power_mw)
        validator = ValueValidator(
            ranges=ranges, now=pd.Timestamp(timezone.now()).tz_localize(None)
        )

        structure_errors = validate_structure(header, specs, duplicates, has_rows=True)
        if structure_errors:
            # 구조가 틀리면 값 검증을 시도할 필요가 없다.
            report = validator.build_report(structure_errors)
            report["row_total"] = 0
            _save_validation(batch, report, encoding, delimiter)
            return report

        usecols = [spec.source_column for spec in specs if spec.source_column in header]
        row_offset = 0
        for chunk in reader.iter_chunks(batch.stored_path, encoding, delimiter, usecols=usecols):
            validator.process(chunk, specs, row_offset)
            row_offset += len(chunk)
            report_progress(self, min(90, 10 + row_offset // 5000), "값 검증")

        if validator.row_total == 0:
            structure_errors = validate_structure(header, specs, duplicates, has_rows=False)

        report = validator.build_report(structure_errors)
        _save_validation(batch, report, encoding, delimiter)
        report_progress(self, 100, "완료")
        return report

    except reader.UnsupportedEncoding as exc:
        _fail(batch, "ENCODING_NOT_SUPPORTED", str(exc))
        raise
    except Exception as exc:  # noqa: BLE001 - 배치 상태를 남기고 그대로 올린다.
        logger.exception("upload validation failed batch_id=%s", batch_id)
        _fail(batch, "VALIDATION_FAILED", str(exc))
        raise


def _aware(value):
    """분석 구간은 KST naive 로 다루지만 DB 저장은 aware 여야 한다 (AGENTS.md §4)."""
    if not value:
        return None
    stamp = pd.Timestamp(value).to_pydatetime()
    return timezone.make_aware(stamp) if timezone.is_naive(stamp) else stamp


def _save_validation(batch: UploadBatch, report: dict, encoding: str, delimiter: str) -> None:
    report["encoding"] = encoding
    report["delimiter"] = delimiter
    period = report.get("period") or {}
    batch.validation_report = report
    batch.row_total = report.get("row_total", 0)
    batch.row_skipped = report.get("row_dropped", 0)
    batch.row_duplicated = report.get("row_duplicated", 0)
    batch.period_start = _aware(period.get("start"))
    batch.period_end = _aware(period.get("end"))
    batch.status = BatchStatus.VALIDATED if report.get("is_loadable") else BatchStatus.FAILED
    batch.save(
        update_fields=[
            "validation_report",
            "row_total",
            "row_skipped",
            "row_duplicated",
            "period_start",
            "period_end",
            "status",
        ]
    )


def _fail(batch: UploadBatch, code: str, message: str) -> None:
    batch.status = BatchStatus.FAILED
    batch.error_message = f"{code}: {message}"[:2000]
    batch.save(update_fields=["status", "error_message"])


@shared_task(bind=True, name="ingestion.commit_upload")
def commit_upload(self, batch_id: int, duplicate_policy: str = DuplicatePolicy.SKIP) -> dict:
    """검증을 통과한 배치를 Measurement 로 적재한다.

    적재는 트랜잭션으로 처리하고 실패 시 부분 적재를 남기지 않는다(specs/18 §3).
    """
    batch = UploadBatch.objects.select_related("unit").get(pk=batch_id)
    unit = batch.unit
    report = batch.validation_report or {}

    try:
        encoding = report.get("encoding") or reader.detect_encoding(batch.stored_path)
        delimiter = report.get("delimiter") or reader.detect_delimiter(batch.stored_path, encoding)
        header = reader.read_header(batch.stored_path, encoding, delimiter)

        specs = mapping_specs_from_rows(_mapping_rows(unit))
        ranges = resolve_ranges(get_setting("physical_ranges", unit.id), unit.rated_power_mw)
        validator = ValueValidator(
            ranges=ranges, now=pd.Timestamp(timezone.now()).tz_localize(None)
        )

        usecols = [spec.source_column for spec in specs if spec.source_column in header]
        loaded = 0
        row_offset = 0

        with transaction.atomic():
            for chunk in reader.iter_chunks(
                batch.stored_path, encoding, delimiter, usecols=usecols
            ):
                result = validator.process(chunk, specs, row_offset)
                row_offset += len(chunk)
                if result.frame.empty:
                    continue
                loaded += _bulk_insert(unit, batch, result.frame, duplicate_policy)
                report_progress(self, min(95, 5 + row_offset // 5000), "적재")

            batch.row_loaded = loaded
            batch.row_skipped = validator.row_dropped
            batch.row_duplicated = validator.duplicate_count
            batch.status = BatchStatus.LOADED
            batch.save(update_fields=["row_loaded", "row_skipped", "row_duplicated", "status"])

        logger.info("upload committed batch_id=%s rows=%s", batch_id, loaded)
        report_progress(self, 100, "완료")
        auto_job_id = _trigger_auto_recalc(unit.id) if loaded else None
        return {
            "batch_id": batch.id,
            "row_loaded": loaded,
            "row_skipped": validator.row_dropped,
            "row_duplicated": validator.duplicate_count,
            "auto_recalc_job_id": auto_job_id,
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("upload commit failed batch_id=%s", batch_id)
        _fail(batch, "COMMIT_FAILED", str(exc))
        raise


def _bulk_insert(unit, batch: UploadBatch, frame: pd.DataFrame, duplicate_policy: str) -> int:
    """시간순 정렬 후 bulk_create 로 적재한다 (specs/03 §5)."""
    frame = frame.sort_values(TIMESTAMP)
    # 청크 내 동일 시각은 마지막 값을 우선한다(specs/03 §4.2 기본 정책).
    frame = frame[~frame[TIMESTAMP].duplicated(keep="last")]

    objects: list[Measurement] = []
    for record in frame.to_dict(orient="records"):
        timestamp = record[TIMESTAMP]
        if pd.isna(timestamp):
            continue
        values = {}
        for key in MEASUREMENT_FIELDS:
            value = record.get(key)
            if value is None or (not isinstance(value, bool) and pd.isna(value)):
                values[key] = None
            else:
                values[key] = bool(value) if key == "duct_burner_on" else float(value)
        objects.append(
            Measurement(
                unit=unit,
                timestamp=(
                    timezone.make_aware(timestamp.to_pydatetime())
                    if timezone.is_naive(timestamp.to_pydatetime())
                    else timestamp.to_pydatetime()
                ),
                upload_batch=batch,
                **values,
            )
        )

    if not objects:
        return 0

    if duplicate_policy == DuplicatePolicy.OVERWRITE:
        created = Measurement.objects.bulk_create(
            objects,
            batch_size=BULK_BATCH_SIZE,
            update_conflicts=True,
            update_fields=[*MEASUREMENT_FIELDS, "upload_batch"],
            unique_fields=["unit", "timestamp"],
        )
        return len(created)

    # 기본: 건너뛰기. 기존 행을 덮어쓰지 않는다.
    # PostgreSQL 에서 ignore_conflicts=True 를 쓰면 Django 가 PK 를 채워주지 않으므로
    # 반환 객체의 pk 로는 적재 건수를 셀 수 없다(항상 0 이 된다).
    # 실제 증가분을 앞뒤 카운트 차이로 구한다.
    before = Measurement.objects.filter(unit=unit).count()
    Measurement.objects.bulk_create(objects, batch_size=BULK_BATCH_SIZE, ignore_conflicts=True)
    return Measurement.objects.filter(unit=unit).count() - before


def _trigger_auto_recalc(unit_id: int) -> str | None:
    """적재 완료 훅 — ON_UPLOAD 설정 호기만 자동 재계산을 건다 (specs/19 §1.2).

    자동 재계산 실패가 적재 결과를 되돌리면 안 되므로 예외를 삼키고 로그만 남긴다.
    """
    # 순환 import 방지 — ingestion 은 analysis 를 모듈 수준에서 알지 못한다.
    from analysis.models import AutoRecalcConfig, AutoRecalcTrigger
    from analysis.tasks_auto import auto_recalc
    from common import jobs

    enabled = AutoRecalcConfig.objects.filter(
        unit_id=unit_id, enabled=True, trigger=AutoRecalcTrigger.ON_UPLOAD
    ).exists()
    if not enabled:
        return None

    try:
        return jobs.enqueue(auto_recalc, unit_id=unit_id, trigger=AutoRecalcTrigger.ON_UPLOAD)
    except Exception:  # noqa: BLE001
        logger.exception("auto recalc enqueue failed unit_id=%s", unit_id)
        return None
