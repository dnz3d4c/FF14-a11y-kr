import pytest
from docs_check import LIMITS, Violation, check_tree, over_limit


def test_a_file_at_the_limit_passes() -> None:
    assert over_limit("docs/status.md", ["줄"] * 120) is None


def test_a_file_over_the_limit_is_reported() -> None:
    found = over_limit("docs/status.md", ["줄"] * 121)

    assert found is not None
    assert found.path == "docs/status.md"
    assert "121" in found.message and "120" in found.message


def test_a_file_without_a_limit_is_ignored() -> None:
    assert over_limit("docs/dev/assemble.md", ["줄"] * 9999) is None


def test_the_real_status_board_is_under_its_limit(tmp_path) -> None:
    """상한을 건 파일이 실제로 그 안인지 본다. 이 저장소의 실물을 잰다."""
    violations = check_tree(_repo_root())

    assert violations == []


def test_a_missing_capped_file_is_reported(tmp_path) -> None:
    """상한을 건 파일이 사라지면 검사가 조용히 통과하지 않는다."""
    violations = check_tree(tmp_path)

    assert [v.path for v in violations] == sorted(LIMITS)


def test_violation_renders_one_line() -> None:
    line = str(Violation("docs/status.md", "130줄로 상한 120줄을 넘었다"))

    assert "\n" not in line
    assert line.startswith("docs/status.md")


def _repo_root():
    import pathlib

    return pathlib.Path(__file__).resolve().parents[3]


if __name__ == "__main__":
    pytest.main([__file__])
