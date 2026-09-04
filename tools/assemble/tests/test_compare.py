"""두 조립 보고를 견주는 부분의 검사."""

from __future__ import annotations

import json
from pathlib import Path

import compare

BEFORE = {
    "orphans": [{"de": "Weg", "en": "Gone"}],
    "untranslated": [{"file": "A.cs", "line": 1, "name": "Alt", "en": "old"}],
    "applied_sites": 10,
    "applied_rows": 9,
    "unreadable": ["A.cs:5"],
}
AFTER = {
    "orphans": [{"de": "Weg", "en": "Gone"}, {"de": "Neu", "en": "New"}],
    "untranslated": [
        {"file": "A.cs", "line": 1, "name": "Alt", "en": "old"},
        {"file": "A.cs", "line": 7, "name": "Neu", "en": "fresh"},
    ],
    "applied_sites": 11,
    "applied_rows": 10,
    "unreadable": ["A.cs:5", "A.cs:9"],
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


def test_명령으로_두_보고를_견준다(tmp_path: Path) -> None:
    before = _write(tmp_path, "before.json", BEFORE)
    after = _write(tmp_path, "after.json", AFTER)
    out = tmp_path / "body.md"

    assert compare.main([str(before), str(after), "--out", str(out)]) == 0
    assert "새로 생긴 고아" in out.read_text(encoding="utf-8")
