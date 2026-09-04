"""원본 파일 안에 덧대는 규칙의 검사.

여기 있는 검사 대부분은 **휴면 경로**다. 조립이 잘 돌 때에는 한 번도 안 걷는
분기라, 조건을 인위로 만들어 두지 않으면 고장 난 채로 조용히 서 있게 된다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import graft


def _rules_file(tmp_path: Path, rules: list[dict[str, object]]) -> Path:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"rules": rules}, ensure_ascii=False), encoding="utf-8")
    return path


def test_고정_문자열_규칙을_적용한다(tmp_path: Path) -> None:
    root = tmp_path / "build"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "A.cs").write_text("행 하나\n행 둘\n", encoding="utf-8")

    rules = graft.load_rules(
        _rules_file(
            tmp_path,
            [
                {
                    "name": "둘-앞에-끼움",
                    "file": "sub/A.cs",
                    "find": "행 둘\n",
                    "replace": "행 하나점오\n행 둘\n",
                }
            ],
        )
    )
    problems = graft.apply_rules(rules, root)

    assert problems == []
    assert (root / "sub" / "A.cs").read_text(encoding="utf-8") == "행 하나\n행 하나점오\n행 둘\n"


def test_배열로_적은_앵커는_줄_목록이다(tmp_path: Path) -> None:
    """JSON 안에서 줄이 줄로 보여야 사람이 읽는다."""
    root = tmp_path / "build"
    root.mkdir()
    (root / "A.cs").write_text("첫 줄\n둘째 줄\n", encoding="utf-8")

    rules = graft.load_rules(
        _rules_file(
            tmp_path,
            [
                {
                    "name": "줄-목록",
                    "file": "A.cs",
                    "find": ["첫 줄"],
                    "replace": ["첫 줄", "끼운 줄"],
                }
            ],
        )
    )

    assert graft.apply_rules(rules, root) == []
    assert (root / "A.cs").read_text(encoding="utf-8") == "첫 줄\n끼운 줄\n둘째 줄\n"


def test_앵커를_못_찾으면_규칙_이름을_대고_실패한다(tmp_path: Path) -> None:
    """아무 데나 넣지 않는다. 잘못 끼우면 컴파일이 깨진다."""
    root = tmp_path / "build"
    root.mkdir()
    (root / "A.cs").write_text("있는 줄\n", encoding="utf-8")

    rules = graft.load_rules(
        _rules_file(
            tmp_path, [{"name": "없는-앵커", "file": "A.cs", "find": "없는 줄\n", "replace": "x"}]
        )
    )
    problems = graft.apply_rules(rules, root)

    assert len(problems) == 1
    assert "없는-앵커" in problems[0]
    assert (root / "A.cs").read_text(encoding="utf-8") == "있는 줄\n"


def test_앵커가_여러_곳에서_잡히면_실패한다(tmp_path: Path) -> None:
    """어디에 넣을지 모르므로 멈춘다."""
    root = tmp_path / "build"
    root.mkdir()
    (root / "A.cs").write_text("같은 줄\n같은 줄\n", encoding="utf-8")

    rules = graft.load_rules(
        _rules_file(
            tmp_path, [{"name": "중복-앵커", "file": "A.cs", "find": "같은 줄\n", "replace": "x\n"}]
        )
    )
    problems = graft.apply_rules(rules, root)

    assert len(problems) == 1
    assert "중복-앵커" in problems[0]
    assert "2" in problems[0]
    assert (root / "A.cs").read_text(encoding="utf-8") == "같은 줄\n같은 줄\n"


def test_대상_파일이_없으면_실패한다(tmp_path: Path) -> None:
    root = tmp_path / "build"
    root.mkdir()

    rules = graft.load_rules(
        _rules_file(tmp_path, [{"name": "없는-파일", "file": "B.cs", "find": "x", "replace": "y"}])
    )
    problems = graft.apply_rules(rules, root)

    assert len(problems) == 1
    assert "없는-파일" in problems[0]


def test_정규식_규칙은_역참조를_쓴다(tmp_path: Path) -> None:
    """`<Version>`은 원본 태그마다 값이 바뀐다. 고정 문자열로는 다음 판에서 깨진다."""
    root = tmp_path / "build"
    root.mkdir()
    (root / "P.csproj").write_text("    <Version>5.95.0</Version>\n", encoding="utf-8")

    rules = graft.load_rules(
        _rules_file(
            tmp_path,
            [
                {
                    "name": "버전-네자리",
                    "file": "P.csproj",
                    "regex": r"<Version>(\d+\.\d+\.\d+)</Version>",
                    "replace": r"<Version>\1.0</Version>",
                }
            ],
        )
    )
    problems = graft.apply_rules(rules, root)

    assert problems == []
    assert (root / "P.csproj").read_text(encoding="utf-8") == "    <Version>5.95.0.0</Version>\n"


def test_이미_네자리면_정규식이_안_잡혀_실패한다(tmp_path: Path) -> None:
    """모양이 달라진 것을 조용히 넘기지 않는다."""
    root = tmp_path / "build"
    root.mkdir()
    (root / "P.csproj").write_text("    <Version>5.95.0.0</Version>\n", encoding="utf-8")

    rules = graft.load_rules(
        _rules_file(
            tmp_path,
            [
                {
                    "name": "버전-네자리",
                    "file": "P.csproj",
                    "regex": r"<Version>(\d+\.\d+\.\d+)</Version>",
                    "replace": r"<Version>\1.0</Version>",
                }
            ],
        )
    )

    assert len(graft.apply_rules(rules, root)) == 1


def test_찾는_방법을_둘_다_적으면_거부한다(tmp_path: Path) -> None:
    path = _rules_file(
        tmp_path, [{"name": "둘다", "file": "A.cs", "find": "x", "regex": "x", "replace": "y"}]
    )

    with pytest.raises(ValueError, match="둘 중 하나"):
        graft.load_rules(path)


def test_찾는_방법이_없으면_거부한다(tmp_path: Path) -> None:
    path = _rules_file(tmp_path, [{"name": "없음", "file": "A.cs", "replace": "y"}])

    with pytest.raises(ValueError, match="둘 중 하나"):
        graft.load_rules(path)


def test_이름이_겹치면_거부한다(tmp_path: Path) -> None:
    """이름이 실패 보고의 유일한 손잡이다. 겹치면 어느 규칙인지 못 댄다."""
    path = _rules_file(
        tmp_path,
        [
            {"name": "같은이름", "file": "A.cs", "find": "x", "replace": "y"},
            {"name": "같은이름", "file": "B.cs", "find": "x", "replace": "y"},
        ],
    )

    with pytest.raises(ValueError, match="같은이름"):
        graft.load_rules(path)


def test_그_때에_도는_규칙만_적용한다(tmp_path: Path) -> None:
    """주입 앞뒤로 갈린다. 다른 때의 규칙은 여기서 손대지 않는다."""
    root = tmp_path / "build"
    root.mkdir()
    (root / "A.cs").write_text("하나\n둘\n", encoding="utf-8")

    rules = graft.load_rules(
        _rules_file(
            tmp_path,
            [
                {
                    "name": "앞",
                    "file": "A.cs",
                    "find": "하나",
                    "replace": "앞것",
                    "phase": "before",
                },
                {"name": "뒤", "file": "A.cs", "find": "둘", "replace": "뒷것"},
            ],
        )
    )

    assert graft.apply_rules(rules, root, graft.BEFORE) == []
    assert (root / "A.cs").read_text(encoding="utf-8") == "앞것\n둘\n"
    assert graft.apply_rules(rules, root, graft.AFTER) == []
    assert (root / "A.cs").read_text(encoding="utf-8") == "앞것\n뒷것\n"


def test_모르는_phase는_거부한다(tmp_path: Path) -> None:
    path = _rules_file(
        tmp_path, [{"name": "언제", "file": "A.cs", "find": "x", "replace": "y", "phase": "중간"}]
    )

    with pytest.raises(ValueError, match="phase"):
        graft.load_rules(path)


def test_한_규칙이_실패해도_나머지를_다_본다(tmp_path: Path) -> None:
    """첫 실패에서 멈추면 두 번째 문제를 다음 판에서야 만난다."""
    root = tmp_path / "build"
    root.mkdir()
    (root / "A.cs").write_text("하나\n", encoding="utf-8")

    rules = graft.load_rules(
        _rules_file(
            tmp_path,
            [
                {"name": "실패-하나", "file": "A.cs", "find": "없다", "replace": "x"},
                {"name": "실패-둘", "file": "A.cs", "find": "이것도 없다", "replace": "x"},
            ],
        )
    )
    problems = graft.apply_rules(rules, root)

    assert len(problems) == 2
