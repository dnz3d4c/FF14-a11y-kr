"""번역의 구두점이 독일어 원문에서 벗어나는 것을 잡는다.

## 무엇을 막나

**2026-09-13에 대장 1,085행을 전수 대조하니 54행이 원문과 구두점이 달랐다.**
숫자도 용어도 낱말도 문체도 기계가 재는데 구두점만 맨몸이었다.

제일 아픈 것이 **끝 마침표를 버린 13곳**이었다. 마침표는 문장 경계라 음성
합성이 거기서 쉬는데, 버리면 안 쉬고 다음 발화와 붙는다. 듣는 쪽에서는
두 안내가 한 문장으로 들린다. 눈으로 읽는 사람에게는 안 보이는 결함이다.

    Wegpunkte: {count} im Gebiet.   ->  경유지, {count}곳      (전)
                                    ->  경유지: {count}곳.     (후)

## 기준은 원문이다

**부호를 더하지도 빼지도 않는다.** 예외는 하나뿐이고, **그 부호 용법이
독일어·영어 고유 관습일 때**다. 기준은 사용자가 정했다(2026-09-13).

## 금지만 잰다

부류를 자동으로 갈라 "이건 허용" 판정을 내리려 들지 않는다. 그렇게 짜 보니
**등위절 `und`를 나열 `und`로 봐서 결함 하나를 통과시켰다.** 검사기가 독일어
구문을 추측하기 시작하면 틀리는 자리가 조용히 는다.

그래서 **어긋난 것만 다섯 갈래로 세고, 정당한 예외는 사람이 판정해
`korean/punctuation.json`에 넣는다.** 이 저장소가 낱말(`ko_words`)과
문체(`ko_lexicon`)에서 이미 쓰는 방식이다.

| 잰다 | 왜 |
|---|---|
| 콜론 개수가 다르다 | `라벨: 값`은 한국어에도 있는 형식이라 고유 관습이 아니다 |
| 마침표가 줄었다 | 문장 경계를 버린 것이다. 음성이 안 쉰다 |
| 물음표·느낌표 개수가 다르다 | 원문에 있으면 옮긴다 |
| 쉼표가 늘었다 | 한국어 문법에 주어 뒤 쉼표는 없다 |
| 세미콜론 개수가 다르다 | 지금 대장에 0건이라 잠든 갈래다 |

**안 재는 것 셋이 곧 고유 관습이다.** 쉼표가 줄어든 것(독일어 정서법이 절
앞에 강제하는 쉼표를 `~어서`·`~으므로`가 흡수한다), 마침표가 늘어난 것(원문
쉼표나 줄표를 마침표로 가른 해법), `Nr.` 같은 약어 마침표.

## 보간 자리 안은 지운다

`{fullAngleDeg:0.#}`의 콜론과 마침표는 서식 지정자지 문장 부호가 아니다.
C# 삼항의 `?`도 마찬가지다. **안 지우면 오탐이 쏟아진다** - 실측에서 물음표를
그렇게 세니 23건이 나왔는데 실제로는 1건이었다.

사용법:
    uv run python tools/ko-punct/ko_punct.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: 번역 대장. `de`가 키이고 `ko`가 잴 대상이다.
STRINGS_FILE = REPO / "korean" / "strings.json"

#: 사람이 판정해 뺀 행. 규약은 그 파일의 `note`·`rule`이 갖는다.
HELD_FILE = REPO / "korean" / "punctuation.json"

#: 판정 갈래. `나열`은 영구 면제이고 `보류`는 사용자 판정을 기다리는 빚이다.
KINDS = ("나열", "보류")

#: 재는 부호 갈래. 판정 목록은 **행이 아니라 이 갈래 단위로** 뺀다 - 행을
#: 통째로 빼면 그 줄에 다른 결함이 생겨도 영영 안 보인다. 실측에서 나열
#: 쉼표로 뺀 행의 콜론 결함이 그렇게 가려졌다.
FAULT_NAMES = ("콜론", "마침표", "물음표·느낌표", "쉼표", "세미콜론")

#: 보류가 이만큼을 넘으면 빚이 쌓인 것이다. 2026-09-13 기준 다섯이다.
PENDING_LIMIT = 5

_SLOT = re.compile(r"\{[^}]*\}")
_PUNCT = re.compile(r"[,.:;!?]")

#: `Nummer`의 약어. 문장 끝이 아니라서 마침표 수에서 뺀다.
_ABBREVIATIONS = ("Nr.",)


def strip_slots(text: str) -> str:
    """보간 자리를 지운다. 그 안의 부호는 서식 지정자지 문장 부호가 아니다."""
    return _SLOT.sub("", text)


def signature(text: str) -> str:
    """문장 부호만 차례대로 뽑은 것. 사람이 눈으로 맞대 보라고 있다."""
    return "".join(_PUNCT.findall(strip_slots(text)))


def counts(text: str) -> Counter[str]:
    return Counter(_PUNCT.findall(strip_slots(text)))


def sentence_dots(text: str) -> int:
    """문장 경계로 쓰인 마침표 수. 약어 마침표는 빼고 센다."""
    bare = strip_slots(text)
    total = bare.count(".")
    for abbreviation in _ABBREVIATIONS:
        total -= bare.count(abbreviation)
    return total


def faults(de: str, ko: str) -> list[str]:
    """원문에서 벗어난 부호의 이름들. 빈 목록이면 어긋나지 않았다."""
    origin, target = counts(de), counts(ko)
    found: list[str] = []

    if origin[":"] != target[":"]:
        found.append("콜론")
    if sentence_dots(de) > sentence_dots(ko):
        found.append("마침표")
    if origin["?"] != target["?"] or origin["!"] != target["!"]:
        found.append("물음표·느낌표")
    if target[","] > origin[","]:
        found.append("쉼표")
    if origin[";"] != target[";"]:
        found.append("세미콜론")

    return found


def load_rows(path: Path = STRINGS_FILE) -> list[dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))["strings"]


def load_held(path: Path = HELD_FILE) -> dict[str, dict[str, str]]:
    """판정 목록. `de` 값을 키로 뒤집어 돌려준다."""
    entries = json.loads(path.read_text(encoding="utf-8"))["held"]
    return {entry["de"]: entry for entry in entries}


def check_strings(
    rows: list[dict[str, str]] | None = None,
    held: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    """원문에서 벗어났는데 판정 목록에도 없는 행."""
    rows = load_rows() if rows is None else rows
    held = load_held() if held is None else held

    problems: list[str] = []
    for index, row in enumerate(rows):
        exempt = set(held.get(row["de"], {}).get("faults", ()))
        found = [name for name in faults(row["de"], row["ko"]) if name not in exempt]
        if not found:
            continue
        problems.append(
            f"[{index}] {'·'.join(found)} 갈래가 원문과 다르다\n"
            f"      de {signature(row['de']):<8} {row['de']}\n"
            f"      ko {signature(row['ko']):<8} {row['ko']}"
        )
    return problems


def check_held(
    rows: list[dict[str, str]] | None = None,
    held: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    """판정 목록 자체의 위생.

    **죽은 항목과 쓸모없는 항목을 둘 다 잡는다.** 번역이 바뀌어 원문 쌍이
    사라지면 면제가 남아도 아무도 못 보고, 고쳐 놓고 면제를 안 지우면 목록이
    쓰레기를 모은다. 둘 다 다음 사람이 목록을 못 믿게 만든다.
    """
    rows = load_rows() if rows is None else rows
    held = load_held() if held is None else held

    by_origin = {row["de"]: row for row in rows}
    problems: list[str] = []

    for de, entry in held.items():
        if entry["kind"] not in KINDS:
            problems.append(f"`{de[:40]}`: 갈래 `{entry['kind']}`는 {KINDS} 중에 없다")
        if not entry.get("why", "").strip():
            problems.append(f"`{de[:40]}`: why가 비었다 - 왜 뺐는지 적어라")
        if not entry.get("when", "").strip():
            problems.append(f"`{de[:40]}`: when이 비었다")

        exempt = list(entry.get("faults", ()))
        if not exempt:
            problems.append(f"`{de[:40]}`: faults가 비었다 - 무슨 부호를 빼는지 적어라")
        unknown = [name for name in exempt if name not in FAULT_NAMES]
        if unknown:
            problems.append(
                f"`{de[:40]}`: 부호 갈래 {'·'.join(unknown)}는 {'·'.join(FAULT_NAMES)} 중에 없다"
            )

        row = by_origin.get(de)
        if row is None:
            problems.append(f"`{de[:40]}`: 대장에 없다 - 번역이 바뀌었으면 이 줄도 지워라")
            continue
        stale = [name for name in exempt if name not in faults(de, row["ko"])]
        if stale:
            problems.append(
                f"`{de[:40]}`: {'·'.join(stale)} 갈래가 안 걸린다 - 고쳤으면 이 줄을 지워라"
            )

    pending = [de for de, entry in held.items() if entry["kind"] == "보류"]
    if len(pending) > PENDING_LIMIT:
        problems.append(
            f"보류가 {len(pending)}건으로 상한 {PENDING_LIMIT}을 넘었다 - "
            f"사용자 판정을 받아 줄이든지 상한의 근거를 다시 적어라"
        )
    return problems


def main(argv: list[str]) -> int:
    problems = check_held() + check_strings()
    if problems:
        print("번역 구두점이 원문과 어긋난다:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(file=sys.stderr)
        print("  고유 관습이라 정당한 자리면 korean/punctuation.json에", file=sys.stderr)
        print("  사유와 날짜를 적어 넣는다. 쉼표를 지웠더니 말이 붙으면", file=sys.stderr)
        print("  낱말은 손대지 말고 `보류`로 세워 두고 묻는다.", file=sys.stderr)
        return 1

    rows = load_rows()
    held = load_held()
    pending = sum(1 for entry in held.values() if entry["kind"] == "보류")
    print(f"통과 - 대장 {len(rows)}행의 구두점이 원문을 따른다")
    print(f"  판정으로 뺀 것 {len(held)}건 (나열 {len(held) - pending}, 보류 {pending})")
    print("  이 검사는 부호만 본다. 낱말·어순·내용 누락은 안 본다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
