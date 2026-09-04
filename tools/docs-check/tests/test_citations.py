"""문서에 손으로 적은 숫자를 조립 보고와 대조하는 부분의 검사.

이 검사는 **막지 않는다.** 번역 잔량은 업스트림이 매일 흔드는 값이라, 문서가 하루
뒤처졌다고 머지를 막으면 빨간불이 신호가 아니게 된다. 대신 어긋난 자리를 지목한다.
"""

from __future__ import annotations

from pathlib import Path

from docs_check import cited, drifted, report_numbers

REPORT = {
    "applied_sites": 817,
    "applied_rows": 793,
    "orphans": [{"de": "a", "en": "b"}] * 5,
    "untranslated": [{"file": "A.cs", "line": 1, "name": "n", "en": "e"}] * 13,
    "unreadable": ["A.cs:1"] * 43,
    "charamake": {
        "Icon.cs": {"F": 84, "S": 1844, "합계": 1928},
        "Shape.cs": {"S": 1095, "합계": 1095},
    },
}

BOARD = """# 현황

| 이름 | 값 | 뜻 |
|------|-----|-----|
| 적용 | 817곳 (대장 793행) | 들어간 자리 |
| 고아 | 5행 | 못 만난 쌍 |
| 미적용 | 13곳 | 영어로 나간다 |
| 못 읽음 | 43곳 | 파서 손 밖 |
| 튜플 사전 | 3,023건 | 안 본다 |
"""


def test_보고에서_숫자를_뽑는다() -> None:
    assert report_numbers(REPORT) == {
        "적용": [817, 793],
        "고아": [5],
        "미적용": [13],
        "못 읽음": [43],
        "튜플 사전": [3023],
    }


def test_표에서_숫자를_뽑는다() -> None:
    """천 단위 쉼표가 붙은 값도 같은 수로 읽는다."""
    assert cited(BOARD) == {
        "적용": [817, 793],
        "고아": [5],
        "미적용": [13],
        "못 읽음": [43],
        "튜플 사전": [3023],
    }


def test_맞으면_조용하다() -> None:
    assert drifted(BOARD, REPORT) == []


def test_어긋난_자리를_지목한다() -> None:
    board = BOARD.replace("| 고아 | 5행", "| 고아 | 4행")

    found = drifted(board, REPORT)

    assert len(found) == 1
    assert "고아" in found[0]
    assert "4" in found[0] and "5" in found[0]


def test_한_줄에_여러_숫자가_있어도_다_본다() -> None:
    board = BOARD.replace("817곳 (대장 793행)", "817곳 (대장 999행)")

    found = drifted(board, REPORT)

    assert len(found) == 1
    assert "적용" in found[0]


def test_문서에_없는_줄은_지목한다() -> None:
    """적어 두기로 한 숫자가 사라진 것도 어긋난 것이다."""
    board = BOARD.replace("| 못 읽음 | 43곳 | 파서 손 밖 |\n", "")

    found = drifted(board, REPORT)

    assert len(found) == 1
    assert "못 읽음" in found[0]


def test_실물_현황판이_실물_보고와_맞는지_잰다(tmp_path: Path) -> None:
    """조립을 아직 안 돌렸으면 잴 것이 없다. 그때는 이 검사가 건너뛴다."""
    root = Path(__file__).resolve().parents[3]
    report = root / "build" / "assemble-report.json"
    if not report.is_file():
        return

    import json

    found = drifted(
        (root / "docs" / "status.md").read_text(encoding="utf-8"),
        json.loads(report.read_text(encoding="utf-8")),
    )

    assert found == [], f"현황판의 기준선이 실측과 어긋났다: {found}"
