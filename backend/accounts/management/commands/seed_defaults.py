"""기본 관리자 계정 + 설정값 시드 (specs/01 AUTH-9, specs/08 ADM-8).

**이 명령은 멱등이어야 한다.** 여러 번 실행해도 중복 생성이 없어야 하고,
관리자가 이미 바꿔 둔 설정값을 되돌려서도 안 된다.
컨테이너 시작 명령(migrate → seed_defaults → 서버)에서 매번 실행된다.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import ApprovalStatus, Role, User
from accounts.services import active_admins
from common.models import Setting
from common.setting_defaults import SETTING_DEFS, serialize_value

# specs/01 AUTH-9 — 활성 관리자가 한 명도 없을 때만 생성한다.
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin1234!"  # noqa: S105 - 최초 1회용 초기 비밀번호, 변경을 강제한다.
DEFAULT_ADMIN_FULL_NAME = "관리자"
DEFAULT_ADMIN_ORGANIZATION = "시스템"


class Command(BaseCommand):
    help = "기본 관리자 계정과 설정값 시드를 생성한다(멱등)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--settings-only",
            action="store_true",
            help="관리자 계정 생성은 건너뛰고 설정값 시드만 반영한다.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        created, updated = self._seed_settings()
        self.stdout.write(f"설정값: 신규 {created}건, 메타 갱신 {updated}건")

        if options["settings_only"]:
            return

        self._seed_admin()

    # --- 설정값 ---

    def _seed_settings(self) -> tuple[int, int]:
        """정의에 없는 Setting 행을 만들고, 이미 있으면 **현재값(value)은 건드리지 않는다.**

        라벨·설명·범위 같은 메타데이터만 코드 정의에 맞춰 갱신한다.
        """
        created = 0
        updated = 0
        existing = {row.key: row for row in Setting.objects.all()}

        for definition in SETTING_DEFS:
            default_str = serialize_value(definition.default, definition.value_type)
            meta: dict[str, Any] = {
                "default_value": default_str,
                "value_type": definition.value_type,
                "category": definition.category,
                "label": definition.label,
                "description": definition.description,
                "unit_label": definition.unit_label,
                "min_value": definition.min_value,
                "max_value": definition.max_value,
            }
            row = existing.get(definition.key)

            if row is None:
                Setting.objects.create(key=definition.key, value=default_str, **meta)
                created += 1
                continue

            if any(getattr(row, name) != value for name, value in meta.items()):
                for name, value in meta.items():
                    setattr(row, name, value)
                row.save(update_fields=[*meta.keys(), "updated_at"])
                updated += 1

        return created, updated

    # --- 기본 관리자 ---

    def _seed_admin(self) -> None:
        if active_admins().exists():
            # 활성 관리자가 있으면 아무것도 하지 않는다. 지운 기본 계정을 되살리지 않는다(AC-01-5).
            self.stdout.write("활성 관리자가 이미 있습니다. 기본 관리자를 생성하지 않습니다.")
            return

        if User.objects.filter(username=DEFAULT_ADMIN_USERNAME).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"ID '{DEFAULT_ADMIN_USERNAME}' 계정이 있으나 활성 관리자가 아닙니다. "
                    "Django /admin/ 이나 셸에서 수동으로 확인하세요."
                )
            )
            return

        User.objects.create_user(
            username=DEFAULT_ADMIN_USERNAME,
            full_name=DEFAULT_ADMIN_FULL_NAME,
            organization=DEFAULT_ADMIN_ORGANIZATION,
            password=DEFAULT_ADMIN_PASSWORD,
            role=Role.ADMIN,
            approval_status=ApprovalStatus.APPROVED,
            must_change_password=True,
            is_staff=True,  # Django /admin/ 접근용. 앱 권한 판정에는 쓰지 않는다.
            is_superuser=True,
        )
        # 비밀번호는 로그에 남기지 않는다(AGENTS.md §7).
        self.stdout.write(
            self.style.SUCCESS(
                f"기본 관리자 계정을 생성했습니다: ID '{DEFAULT_ADMIN_USERNAME}' "
                "(최초 로그인 후 비밀번호를 변경하세요)"
            )
        )
