import pytest
from render_prompt import build_fields, render

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
