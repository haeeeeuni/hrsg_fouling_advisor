"""응답이 끊긴 RUNNING 분석을 실패로 정리한다.

분석 실행 요청이 들어올 때 해당 호기에 대해 자동으로 수행되지만,
그 호기를 아무도 다시 실행하지 않으면 레코드가 계속 남는다.
배포 직후나 워커 재시작 뒤 한 번 돌려 전체를 정리하는 용도다.

    python manage.py release_stale_runs
    python manage.py release_stale_runs --minutes 10 --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from analysis.models import AnalysisRun, RunStatus
from analysis.pipeline import release_stale_runs
from units.models import Unit
from units.settings_resolver import get_effective_settings


class Command(BaseCommand):
    help = "워커가 죽어 RUNNING 으로 남은 분석 실행을 실패로 정리한다."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--minutes",
            type=int,
            default=None,
            help="이 시간을 넘긴 RUNNING 을 정리한다(기본: analysis_stale_minutes 설정값).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="정리하지 않고 대상만 보여준다.",
        )

    def handle(self, *args, **options) -> None:
        running = AnalysisRun.objects.filter(status=RunStatus.RUNNING).select_related("unit")
        if not running.exists():
            self.stdout.write("정리할 RUNNING 분석이 없습니다.")
            return

        total = 0
        for unit in Unit.objects.filter(pk__in=running.values("unit_id")):
            minutes = (
                options["minutes"] or get_effective_settings(unit.id)["analysis_stale_minutes"]
            )

            if options["dry_run"]:
                for run in running.filter(unit=unit):
                    self.stdout.write(
                        f"  [dry-run] {unit.code} id={run.id} 시작={run.executed_at:%Y-%m-%d %H:%M}"
                    )
                continue

            released = release_stale_runs(unit, minutes)
            if released:
                self.stdout.write(f"  {unit.code}: {released}건 정리 ({minutes}분 초과)")
            total += released

        if not options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"총 {total}건 정리했습니다."))
