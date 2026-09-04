"""실제 원본 트리와 실제 대장으로 도는 검사.

가짜 저장소로는 못 잡는 것이 있다. 파서를 넓히면 원본의 어느 자리가 조용히 다르게
읽히는데, 그 자리는 우리가 지어낸 예시에 없다. 그래서 여기서는 원본 94개 파일을
그대로 읽는다. 서브모듈이 비어 있으면 건너뛴다.

## 개수를 박지 않는다

"몇 곳"을 단언하는 검사는 여기 하나도 없다. 업스트림 핀이 움직이면 개수가 흔들리고,
흔들리는 검사는 곧 무시당해서 신호이기를 그만둔다. 개수 판정은 `compare.py`가 맡는다.
여기서 보는 것은 개수가 아니라 **불변**이다 - 조립 전후로 같아야 하는 것들.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import assemble
import files
import scanner

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "upstream" / assemble.SOURCE_NAME
CATALOG = REPO / "korean" / "strings.json"


def _rows() -> list[dict[str, str]]:
    if not CATALOG.is_file():
        pytest.skip("대장이 없다")
    rows: list[dict[str, str]] = json.loads(CATALOG.read_text(encoding="utf-8"))["strings"]
    return rows


def _catalog() -> dict[tuple[str, str], str]:
    if not CATALOG.is_file():
        pytest.skip("대장이 없다")
    return assemble.load_catalog(CATALOG)


def _sources() -> list[Path]:
    if not SOURCE.is_dir():
        pytest.skip("원본 서브모듈이 비어 있다")
    return assemble.source_files(SOURCE)


def test_대장의_모든_행이_C샵에_그대로_들어갈_모양이다() -> None:
    """대장은 사람이 손으로 고치는 파일이고, 이제 그 값이 컴파일을 깨뜨릴 수 있다."""
    for row in _rows():
        where = row["en"][:60]
        assert assemble.literal_fault(row["ko"]) is None, where
        assert scanner.body_fault(row["ko"]) is None, where


def test_독일어와_영어는_조립_전후로_한_자도_안_바뀐다() -> None:
    """이 저장소의 전제다. 두 언어 사용자가 듣는 문장은 조립 전후로 같아야 한다."""
    catalog = _catalog()
    for path in _sources():
        before = files.read(path)
        after = scanner.rewrite(before, catalog).text

        assert [(site.de_raw, site.en_raw) for site in scanner.find_sites(after)] == [
            (site.de_raw, site.en_raw) for site in scanner.find_sites(before)
        ], path.name


def test_소스에서_만나는_쌍이_조립_전후로_같다() -> None:
    """파서를 넓히다 자리를 잃으면 여기가 잡는다. 잃은 자리는 영어로 나가고 만다."""
    catalog = _catalog()
    for path in _sources():
        result = scanner.rewrite(files.read(path), catalog)

        assert {(site.de, site.en) for site in scanner.find_sites(result.text)} == set(
            result.seen
        ), path.name


def test_이미_조립된_텍스트를_다시_조립해도_안_바뀐다() -> None:
    """조립은 여러 번 도는 단계다. 두 번째가 달라지면 무엇을 빌드했는지 알 수 없다."""
    catalog = _catalog()
    for path in _sources():
        once = scanner.rewrite(files.read(path), catalog).text
        twice = scanner.rewrite(once, catalog).text

        assert twice == once, path.name
