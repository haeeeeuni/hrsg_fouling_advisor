"""플랜트 데이터 요청 체크리스트 (specs/07, specs/09 §7).

요청 건을 만들 때 그 시점의 활성 템플릿 항목을 **복사**한다. 관리자가 템플릿을 바꿔도
진행 중인 요청 건은 바뀌지 않는다(CHK-3, AC-07-3).
체크리스트는 수신 여부만 관리하고 값은 저장하지 않는다.
"""

from django.conf import settings as django_settings
from django.db import models


class Category(models.TextChoices):
    """분류와 표시 순서 (specs/07 §2.1). 한·영 이름은 CATEGORY_EN 에 있다."""

    GT = "GT", "가스터빈"
    FUEL = "FUEL", "연료"
    EXHAUST = "EXHAUST", "배기가스"
    FEEDWATER = "FEEDWATER", "급수"
    STEAM = "STEAM", "증기"
    EMISSION = "EMISSION", "배출가스"
    MODULE = "MODULE", "열교환 모듈 사양"
    DESIGN = "DESIGN", "설계값"
    PINCH = "PINCH", "핀치·어프로치"
    SCHEDULE = "SCHEDULE", "일정·현장 조건"
    DATA_SCOPE = "DATA_SCOPE", "데이터 범위"


CATEGORY_EN = {
    Category.GT: "Gas Turbine",
    Category.FUEL: "Fuel",
    Category.EXHAUST: "Exhaust Gas",
    Category.FEEDWATER: "Feedwater",
    Category.STEAM: "Steam",
    Category.EMISSION: "Emissions",
    Category.MODULE: "Heat Exchanger Modules",
    Category.DESIGN: "Design Data",
    Category.PINCH: "Pinch & Approach",
    Category.SCHEDULE: "Schedule & Site Conditions",
    Category.DATA_SCOPE: "Data Scope",
}
CATEGORY_ORDER = {code: index for index, code in enumerate(Category.values)}


class Source(models.TextChoices):
    FORM = "FORM", "사내 양식"
    ADDED = "ADDED", "앱에서 추가"


class ItemFields(models.Model):
    """템플릿과 요청 건 항목이 함께 갖는 필드 — 요청 건은 생성 시점의 값을 복사해 둔다."""

    category = models.CharField("분류", max_length=20, choices=Category.choices)
    name_ko = models.CharField("항목명", max_length=200)
    name_en = models.CharField("항목명(영문)", max_length=200)
    unit = models.CharField("단위", max_length=40, blank=True)
    is_required = models.BooleanField("필수", default=True)
    why_needed_ko = models.CharField("필요한 이유", max_length=300, blank=True)
    why_needed_en = models.CharField("필요한 이유(영문)", max_length=300, blank=True)
    is_calculator_input = models.BooleanField("계산기 입력", default=False)
    order = models.PositiveIntegerField("순서", default=0)

    class Meta:
        abstract = True


class ChecklistTemplateItem(ItemFields):
    """관리자가 관리하는 항목 템플릿 (specs/07 CHK-1·2·6)."""

    source = models.CharField("출처", max_length=10, choices=Source.choices, default=Source.FORM)
    is_active = models.BooleanField("사용", default=True)
    is_placeholder = models.BooleanField("임시값", default=True)
    version = models.PositiveIntegerField("버전", default=1)
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    class Meta:
        verbose_name = "체크리스트 항목 템플릿"
        verbose_name_plural = "체크리스트 항목 템플릿"
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name_ko"], name="checklist_template_unique_name"
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.get_category_display()}] {self.name_ko}"


class RequestStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "진행 중"
    DONE = "DONE", "완료"
    ARCHIVED = "ARCHIVED", "보관"


class DataRequest(models.Model):
    """요청 건 (specs/07 CHK-3). 만든 사람만 보고 고친다(CHK-4)."""

    owner = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="작성자",
        on_delete=models.CASCADE,
        related_name="data_requests",
    )
    title = models.CharField("요청 건 이름", max_length=200)
    memo = models.TextField("메모", blank=True)
    due_date = models.DateField("희망 회신일", null=True, blank=True)
    status = models.CharField(
        "상태", max_length=20, choices=RequestStatus.choices, default=RequestStatus.IN_PROGRESS
    )
    template_snapshot_at = models.DateTimeField("템플릿 복사 시각")
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    class Meta:
        verbose_name = "데이터 요청 건"
        verbose_name_plural = "데이터 요청 건"
        ordering = ["-updated_at", "-id"]

    def __str__(self) -> str:
        return self.title


class ItemState(models.TextChoices):
    PENDING = "PENDING", "미수신"
    RECEIVED = "RECEIVED", "받음"
    NOT_APPLICABLE = "NOT_APPLICABLE", "해당 없음"


class DataRequestItem(ItemFields):
    """요청 건에 복사된 항목. 템플릿이 사라지거나 바뀌어도 이 행은 그대로다."""

    request = models.ForeignKey(
        DataRequest, verbose_name="요청 건", on_delete=models.CASCADE, related_name="items"
    )
    template_item = models.ForeignKey(
        ChecklistTemplateItem,
        verbose_name="원본 템플릿 항목",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    state = models.CharField(
        "상태", max_length=20, choices=ItemState.choices, default=ItemState.PENDING
    )
    received_at = models.DateTimeField("받은 일시", null=True, blank=True)
    memo = models.CharField("메모", max_length=500, blank=True)

    class Meta:
        verbose_name = "데이터 요청 항목"
        verbose_name_plural = "데이터 요청 항목"
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.request_id}: {self.name_ko} ({self.state})"
