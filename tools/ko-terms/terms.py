"""게임 용어 대장을 읽는다.

뽑는 쪽은 C#(`Program.cs`)이다 - Lumina로 sqpack을 읽어야 해서다. 이 파일은
그 결과를 다루는 파이썬 쪽이고, 검사가 여기 붙는다.

대장: `korean/terms.json`
덤프: `tools/ko-terms/out/<시트>-Korean.tsv` (버전 관리 밖 - 게임 텍스트다)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "korean" / "terms.json"
OUT = Path(__file__).resolve().parent / "out"

# `Program.cs`가 다루는 시트와 같아야 한다. UI 문자열은 Addon에 있지만
# 기술·소환수·상태 이름은 거기 없다.
SHEETS = ("Addon", "Action", "Pet", "Status")

# 시트를 안 적은 줄은 Addon이다. 대장의 옛 줄들이 전부 `addon` 하나만 갖는
# 모양이라 그 130줄을 옮겨 적지 않고 기본값으로 읽는다.
DEFAULT_SHEET = "Addon"


def dump_path(sheet: str = DEFAULT_SHEET) -> Path:
    """그 시트의 한국어 덤프. `Program.cs`의 `Dump`가 짓는 이름과 같다."""
    return OUT / f"{sheet.lower()}-Korean.tsv"


# 옛 이름을 남겨 둔다. Addon 덤프를 가리키는 자리가 아직 여럿이다.
DUMP = dump_path()


def source_of(term: dict[str, Any]) -> tuple[str, int]:
    """대장 한 줄이 가리키는 (시트 이름, 행 번호).

    줄의 모양이 둘이다. 옛 줄은 `addon` 하나만 갖고 그건 늘 Addon 시트이며,
    Addon 밖에서 뽑은 줄은 `sheet`와 `row`를 갖는다. `addon`을 다른 시트의
    행 번호로 재활용하면 "Addon 27행"이 Pet 27행을 뜻하게 되어, 이 대장이
    막으려는 바로 그 조용한 거짓이 된다.
    """
    if "addon" in term:
        return DEFAULT_SHEET, term["addon"]
    return term["sheet"], term["row"]


def load_dump(sheet: str = DEFAULT_SHEET) -> dict[int, str]:
    """`행 번호 -> 문자열`. 덤프가 없으면 빈 사전."""
    path = dump_path(sheet)
    if not path.is_file():
        return {}

    rows: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        number, _, text = line.partition("\t")
        if number.isdigit():
            rows[int(number)] = text
    return rows
