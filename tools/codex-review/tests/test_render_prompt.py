import pytest
from render_prompt import (
    TEMPLATE_ROOT,
    build_fields,
    compose,
    ko_only_block,
    render,
    untracked_block,
)

TEMPLATE = "맥락: {{REPO_CONTEXT}}\n의도: {{INTENT}}\ndiff:\n{{DIFF_OR_STAT}}\n"


def test_diff_placeholders_are_left_alone() -> None:
    """diff 안에 자리표시자와 같은 글자가 있어도 치환되지 않는다."""
    diff = "+    text = text.replace('{{REPO_CONTEXT}}', value)"
    out = render(TEMPLATE, {"REPO_CONTEXT": "실제 맥락", "INTENT": "뜻"}, diff)

    assert diff in out
    assert out.count("실제 맥락") == 1


def test_every_placeholder_is_filled() -> None:
    out = render(TEMPLATE, {"REPO_CONTEXT": "맥락", "INTENT": "뜻"}, "diff 본문")

    assert "{{" not in out


def test_unknown_placeholder_is_rejected() -> None:
    """템플릿이 요구하는 자리를 안 채우면 조용히 넘어가지 않는다."""
    with pytest.raises(ValueError, match="REPO_CONTEXT"):
        render(TEMPLATE, {"INTENT": "뜻"}, "diff 본문")


def test_repo_context_falls_back_when_file_is_absent(tmp_path) -> None:
    fields = build_fields(tmp_path, intent="뜻", hypothesis="가설", plan="단계")

    assert fields["REPO_CONTEXT"] == "(저장소 맥락 없음)"


def test_repo_context_is_read_as_a_bullet_list(tmp_path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "codex-review.json").write_text(
        '{"context": ["첫째 줄", "둘째 줄"]}', encoding="utf-8"
    )

    fields = build_fields(tmp_path, intent="뜻", hypothesis="가설", plan="단계")

    assert fields["REPO_CONTEXT"] == "- 첫째 줄\n- 둘째 줄"


def test_untracked_files_are_listed_as_bullets() -> None:
    """diff에 없는 새 파일은 목록으로 실어야 리뷰어가 그 파일이 있는 줄 안다."""
    assert untracked_block(["a.md", "b/c.md"]) == "- a.md\n- b/c.md"
    assert untracked_block([]) == "(none)"


def test_ko_only_keeps_added_korean_and_drops_removed() -> None:
    """축 나는 원문을 가린 채 한국어만 읽고 판정한다."""
    diff = "\n".join(
        [
            '-    "ko": "옛 문장",',
            '+    "de": "Schließen",',
            '+    "ko": "닫기",',
            '+    "ko": "숫자 {digit}"',
        ]
    )

    assert ko_only_block(diff) == "1. 닫기\n2. 숫자 {digit}"


@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in TEMPLATE_ROOT.glob("review*.md") if p.name != "review-plan.md"),
)
def test_every_shipped_template_renders(tmp_path, name) -> None:
    """전역 템플릿이 자리를 새로 더해도 이 도구가 따라가는지 잰다."""
    template = (TEMPLATE_ROOT / name).read_text(encoding="utf-8")
    fields = build_fields(tmp_path, intent="뜻", hypothesis="가설", plan="단계")

    out = compose(template, fields, '+    "ko": "닫기",')

    assert "{{" not in out


def test_ko_only_ignores_korean_quoted_inside_code() -> None:
    """테스트 파일이 예시로 든 "ko" 줄은 번역이 아니다."""
    diff = '+        \'+    "ko": "예시 문장",\','

    assert ko_only_block(diff) == "(이번 변경에 새로 더해진 한국어 문장이 없다)"


def test_shipped_templates_are_found() -> None:
    """템플릿을 하나도 못 찾으면 위 렌더 검사가 0건으로 조용히 끝난다."""
    if not TEMPLATE_ROOT.exists():
        pytest.skip("CI 러너에는 전역 템플릿이 없다")
    names = {p.name for p in TEMPLATE_ROOT.glob("review*.md")}

    assert {"review.md", "review-docs.md", "review-ko.md", "review-notes.md"} <= names
