"""진행률·이메일 문구 — 순수 함수 (specs/07 CHK-3·CHK-5, AC-07-2·4). DB 불필요."""

from checklist import rules

ORDER = {"GT": 0, "PINCH": 1}
LABELS_KO = {"GT": "가스터빈", "PINCH": "핀치·어프로치"}
LABELS_EN = {"GT": "Gas Turbine", "PINCH": "Pinch & Approach"}


def item(name, state="PENDING", required=True, category="GT", unit="", why=""):
    return {
        "category": category,
        "name_ko": name,
        "name_en": f"{name}-en",
        "unit": unit,
        "is_required": required,
        "why_needed_ko": why,
        "why_needed_en": f"{why}-en" if why else "",
        "state": state,
    }


def test_progress_counts_only_required_items():
    items = [item("a", "RECEIVED"), item("b"), item("c", "RECEIVED", required=False)]

    assert rules.progress(items) == {"received": 1, "total": 2, "percent": 50, "complete": False}


def test_not_applicable_leaves_the_denominator():
    """AC-07-2"""
    items = [item("a", "RECEIVED"), item("b", "NOT_APPLICABLE")]

    result = rules.progress(items)

    assert result["total"] == 1
    assert result["complete"] is True
    assert result["percent"] == 100


def test_no_required_items_counts_as_complete():
    assert rules.progress([item("a", required=False)])["complete"] is True
    assert rules.progress([])["percent"] == 100


def test_progress_by_category_follows_category_order():
    items = [item("p", category="PINCH"), item("g", "RECEIVED", category="GT")]

    rows = rules.progress_by_category(items, ORDER)

    assert [r["category"] for r in rows] == ["GT", "PINCH"]
    assert rows[0]["complete"] is True


def email(items, **kwargs):
    defaults = dict(
        lang="ko",
        scope="pending",
        header="머리말",
        footer="맺음말",
        category_labels=LABELS_KO,
        category_order=ORDER,
    )
    return rules.email_text(items, **{**defaults, **kwargs})


def test_pending_scope_lists_only_pending_items_grouped_by_category():
    """AC-07-4"""
    text = email(
        [
            item("드럼 압력", category="PINCH", unit="bar(g)", why="포화온도"),
            item("GT 출력", unit="MW"),
            item("받은 것", "RECEIVED"),
            item("해당 없는 것", "NOT_APPLICABLE"),
        ]
    )

    assert text.startswith("머리말\n\n[가스터빈]\n- GT 출력 (MW) [필수]\n\n[핀치·어프로치]\n")
    assert "- 드럼 압력 (bar(g)) [필수] — 포화온도" in text
    assert "받은 것" not in text
    assert "해당 없는 것" not in text
    assert text.rstrip().endswith("맺음말")


def test_all_scope_includes_received_but_not_not_applicable():
    text = email([item("받은 것", "RECEIVED"), item("해당 없는 것", "NOT_APPLICABLE")], scope="all")

    assert "받은 것" in text
    assert "해당 없는 것" not in text


def test_english_uses_english_names_labels_and_marks():
    text = email(
        [item("GT 출력", unit="MW", why="부분 부하")],
        lang="en",
        category_labels=LABELS_EN,
        header="Dear",
        footer="",
    )

    assert "[Gas Turbine]" in text
    assert "- GT 출력-en (MW) [Required] — 부분 부하-en" in text
    assert "필수" not in text


def test_optional_items_are_not_marked_required():
    assert "[필수]" not in email([item("선택 항목", required=False)])
