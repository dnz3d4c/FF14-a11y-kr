"""두 조립 보고를 견주는 부분의 검사."""

from __future__ import annotations

import json
from pathlib import Path

import compare

BLIND = {
    "file": "A.cs",
    "line": 5,
    "end_line": 5,
    "name": "Alt",
    "shape": "리터럴이 아님",
    "excerpt": "IsGerman ? De : En",
}
FRESH_BLIND = {
    "file": "A.cs",
    "line": 9,
    "end_line": 13,
    "name": "Neu",
    "shape": "이어붙이기",
    "excerpt": 'IsGerman ? "a" + "b" : "c" + "d"',
}

BEFORE = {
    "orphans": [{"de": "Weg", "en": "Gone"}],
    "untranslated": [{"file": "A.cs", "line": 1, "name": "Alt", "en": "old"}],
    "applied_sites": 10,
    "applied_rows": 9,
    "unreadable": [BLIND],
}
AFTER = {
    "orphans": [{"de": "Weg", "en": "Gone"}, {"de": "Neu", "en": "New"}],
    "untranslated": [
        {"file": "A.cs", "line": 1, "name": "Alt", "en": "old"},
        {"file": "A.cs", "line": 7, "name": "Neu", "en": "fresh"},
    ],
    "applied_sites": 11,
    "applied_rows": 10,
    "unreadable": [BLIND, FRESH_BLIND],
}


def _write(tmp_path: Path, name: str, document: dict[str, object]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def test_새로_생긴_고아만_지목한다(tmp_path: Path) -> None:
    """고아는 업스트림이 그 문장을 고쳤다는 신호다. 새 판을 받을 때 가장 먼저 볼 것이다."""
    change = compare.compare(
        json.loads(_write(tmp_path, "a.json", BEFORE).read_text(encoding="utf-8")),
        json.loads(_write(tmp_path, "b.json", AFTER).read_text(encoding="utf-8")),
    )

    assert change.new_orphans == [("Neu", "New")]
    assert change.gone_orphans == []


def test_사라진_고아도_낸다(tmp_path: Path) -> None:
    change = compare.compare(AFTER, BEFORE)

    assert change.new_orphans == []
    assert change.gone_orphans == [("Neu", "New")]


def test_새로_생긴_미적용을_이름과_함께_낸다() -> None:
    change = compare.compare(BEFORE, AFTER)

    assert [(site["name"], site["en"]) for site in change.new_untranslated] == [("Neu", "fresh")]


def test_숫자의_증감을_낸다() -> None:
    change = compare.compare(BEFORE, AFTER)

    assert change.counts == {
        "적용": (10, 11),
        "대장 행": (9, 10),
        "고아": (1, 2),
        "미적용": (1, 2),
        "못 읽음": (1, 2),
    }


def test_달라진_것이_없으면_조용하다() -> None:
    change = compare.compare(BEFORE, BEFORE)

    assert not change.moved
    assert "달라진 것이 없다" in change.as_markdown()


def test_고아가_늘면_본문_맨_앞에서_지목한다() -> None:
    """사람이 가장 먼저 봐야 하는 것이라 맨 앞에 둔다."""
    body = compare.compare(BEFORE, AFTER).as_markdown()

    assert body.index("새로 생긴 고아") < body.index("새로 생긴 미적용")
    assert "New" in body


def test_새로_생긴_못_읽음을_모양과_함께_낸다() -> None:
    """업스트림이 파서 손 밖인 모양을 더했다는 신호다. 그 자리는 미적용에도 안 잡힌다."""
    change = compare.compare(BEFORE, AFTER)

    assert [(site["name"], site["shape"]) for site in change.new_unreadable] == [
        ("Neu", "이어붙이기")
    ]
    assert change.gone_unreadable == []


def test_사라진_못_읽음도_낸다() -> None:
    change = compare.compare(AFTER, BEFORE)

    assert [site["name"] for site in change.gone_unreadable] == ["Neu"]
    assert change.new_unreadable == []


def test_못_읽음이_늘면_고아_다음에_지목한다() -> None:
    """고아 다음으로 사람이 먼저 봐야 하는 것이다."""
    body = compare.compare(BEFORE, AFTER).as_markdown()

    assert body.index("새로 생긴 고아") < body.index("새로 생긴 못 읽음") < body.index("### 숫자")
    assert "A.cs:9-13" in body


def test_옛_보고와도_견주되_개수만_낸다() -> None:
    """옛 보고는 `unreadable`이 문자열 배열이라 자리를 못 가른다. 터지지만 않으면 된다."""
    old = {**BEFORE, "unreadable": ["A.cs:5"]}

    change = compare.compare(old, AFTER)

    assert change.counts["못 읽음"] == (1, 2)
    assert change.new_unreadable == []
    assert change.gone_unreadable == []


def test_명령으로_두_보고를_견준다(tmp_path: Path) -> None:
    before = _write(tmp_path, "before.json", BEFORE)
    after = _write(tmp_path, "after.json", AFTER)
    out = tmp_path / "body.md"

    assert compare.main([str(before), str(after), "--out", str(out)]) == 0
    assert "새로 생긴 고아" in out.read_text(encoding="utf-8")
