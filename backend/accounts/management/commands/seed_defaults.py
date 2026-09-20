"""기본 관리자 계정 + 설정값 시드 (specs/01 §4, specs/13 §4.2, specs/18 §7).

**이 명령은 멱등이어야 한다**(AC-18-4). 여러 번 실행해도 중복 생성이 없어야 하고,
관리자가 이미 바꿔 둔 설정값을 되돌려서도 안 된다.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Role, User
from maintenance.models import FoulingKeyword
from maintenance.services.keywords import DEFAULT_KEYWORDS
from units.models import Setting
from units.setting_defaults import SETTING_DEFS, serialize_value

# specs/01 §4 — 관리자 역할 사용자가 하나도 없을 때만 생성한다.
DEFAULT_ADMIN_EMPLOYEE_NO = "ADM01"
DEFAULT_ADMIN_FULL_NAME = "관리자"
DEFAULT_ADMIN_PASSWORD = "qwer"  # noqa: S105 - 최초 1회용 초기 비밀번호, 변경을 강제한다.


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

        keywords = self._seed_keywords()
        self.stdout.write(f"오염 키워드: 신규 {keywords}건")

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
            row = existing.get(definition.key)

            if row is None:
                Setting.objects.create(
                    key=definition.key,
                    value=default_str,
                    default_value=default_str,
                    value_type=definition.value_type,
                    category=definition.category,
                    label=definition.label,
                    description=definition.description,
                    unit_label=definition.unit_label,
                    min_value=definition.min_value,
                    max_value=definition.max_value,
                )
                created += 1
                continue

            fields: dict[str, Any] = {
                "default_value": default_str,
                "value_type": definition.value_type,
                "category": definition.category,
                "label": definition.label,
                "description": definition.description,
                "unit_label": definition.unit_label,
                "min_value": definition.min_value,
                "max_value": definition.max_value,
            }
            changed = [name for name, value in fields.items() if getattr(row, name) != value]
            if changed:
                for name, value in fields.items():
                    setattr(row, name, value)
                row.save(update_fields=[*fields.keys(), "updated_at"])
                updated += 1

        return created, updated

    # --- 오염 키워드 사전 (specs/10 §3.1) ---

    def _seed_keywords(self) -> int:
        """이미 있는 키워드는 건드리지 않는다(관리자가 지운 것을 되살리지 않도록)."""
        existing = set(FoulingKeyword.objects.values_list("keyword", "category"))
        new_rows = [
            FoulingKeyword(keyword=keyword, category=category)
            for keyword, category in DEFAULT_KEYWORDS
            if (keyword, category) not in existing
        ]
        FoulingKeyword.objects.bulk_create(new_rows)
        return len(new_rows)

    # --- 기본 관리자 ---

    def _seed_admin(self) -> None:
        if User.objects.filter(role=Role.ADMIN).exists():
            # 이미 관리자가 있으면 아무것도 하지 않는다. 덮어쓰기 금지(AC-01-2).
            self.stdout.write("관리자 계정이 이미 존재합니다. 생성하지 않습니다.")
            return

        if User.objects.filter(employee_no=DEFAULT_ADMIN_EMPLOYEE_NO).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"사번 {DEFAULT_ADMIN_EMPLOYEE_NO} 계정이 이미 있으나 관리자가 아닙니다. "
                    "수동으로 확인하세요."
                )
            )
            return

        User.objects.create_user(
            employee_no=DEFAULT_ADMIN_EMPLOYEE_NO,
            full_name=DEFAULT_ADMIN_FULL_NAME,
            password=DEFAULT_ADMIN_PASSWORD,
            role=Role.ADMIN,
            must_change_password=True,
            is_staff=True,  # Django /admin/ 접근용. 앱 권한 판정에는 쓰지 않는다.
            is_superuser=True,
        )
        # 비밀번호는 로그에 남기지 않는다(specs/01 §4, AGENTS.md §7).
        self.stdout.write(
            self.style.SUCCESS(
                f"기본 관리자 계정을 생성했습니다: {DEFAULT_ADMIN_FULL_NAME} / "
                f"{DEFAULT_ADMIN_EMPLOYEE_NO} (최초 로그인 후 비밀번호를 변경하세요)"
            )
        )
