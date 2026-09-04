"""사용자가 판정한 낱말이 다음 판에서 되돌아오는 것을 막는다.

## 무엇을 막나

**판정 목록이 여러 곳으로 흩어지면 갈라지고, 갈라진 것을 아무도 못 본다.**

옛 저장소에서 겪은 것이 그것이다. 릴리스 노트의 낱말 목록과 사용자 문서의
낱말 목록이 도구마다 따로 있었고, 모드 발화에는 목록 자체가 없었다. 그래서
2026-08-24 전수 검수가 낱말 74곳을 판정했는데 그 판정이 동결 문서에만 남고
기계 규칙으로는 안 갔다. `고른 다음 건네주기`가 그대로 살아 있었다.

같은 부류가 릴리스 노트에서 다섯 판 연속 재발했다. `v5.93.0.2`에서 사용자가
`말한다`를 `음성 출력`으로 고친 판정이 문서 표에 박혔는데 `v5.94.0.0`에서
열두 자리가 되돌아갔다.

**조언은 안 지켜진다. 지켜지는 것은 빨개지는 것뿐이다.**

## 목록은 하나다

`korean/lexicon.json`이 단일 원천이고 `ko_style`과 `notes_check`가 거기서
읽는다. 새 판정이 나오면 넣을 자리를 고민하지 않는다 - 대상만 고른다.

## 대상을 가른다

`mod`의 낱말이 `note`에 걸리지 않고 그 반대도 아니다. 같은 낱말이라도 자리에
따라 판정이 다르다 - 노트의 `거절`은 게임이 `취소`라고 부르므로 틀렸지만,
모드가 그 상태를 발화하는 자리는 아예 없어서 대상이 다르다.

## 낱말 경계는 앞만 막는다

뒤는 안 막는다 - 조사가 붙는다. `notes_check._KO_BANNED_RE`와 같은 꼴이고
같은 이유다. 처음 판이 부분 문자열로 재서 이미 나간 판 둘을 빨갛게 만들었다
(`기다리는지`의 `다리`, `경고가`의 `고가`).

## 목록이 자라는 규약

**사용자가 실제로 고친 것만 넣고 `why`에 근거를 적는다.** `why`가 빈 항목은
아래 `check_entries`가 거부하므로 반쯤 넣은 상태가 안 생긴다.

넣으면 안 되는 것도 적는다. `lexicon.json`의 `rejected`가 그 자리다 - `끝`은
부류 D가 판정한 낱말이지만 지금 발화에 남은 일곱 곳이 전부 종점을 가리키는
정당한 자리라, 넣으면 그날로 오탐 일곱이다.

## 이 파일이 안 읽는 것

`lexicon.json`에는 `plain_words`와 `actions`도 있는데 **여기서 안 읽는다.**
그 둘은 사람이 읽는 판정이고 `ko-user-guide`·`ko-localization` 스킬이 갖는다.
기계가 재는 것은 `entries`와 `rejected`뿐이다.

사용법:
    uv run python tools/ko-lexicon/ko_lexicon.py --target mod
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[2]

#: 낱말 판정의 단일 원천.
LEXICON_PATH = REPO / "korean" / "lexicon.json"

#: 검사 대상. 이름은 `lexicon.json`의 `entries` 키와 같다.
TARGETS = ("mod", "note", "doc")

#: 노트가 사는 곳. **파일 하나가 판 하나다**(`docs/release-notes/README.md`).
NOTES_DIR = REPO / "docs" / "release-notes"

#: 노트 파일 이름. 판 번호 네 마디다.
#:
#: **`ko_style`과 `notes_check`가 이것을 가져다 쓴다.** 셋이 다 "어느 파일이
#: 노트인가"를 알아야 하는데, 임포트 방향이 `ko_lexicon` → `ko_style` →
#: `notes_check`라 여기가 셋이 다 닿는 유일한 자리다. 낱말 도구가 파일 이름
#: 규약을 갖는 것이 어색하지만, 사본 셋을 두면 규약이 바뀔 때 한둘만 따라오고
#: **못 따라온 쪽은 노트를 하나도 못 찾은 채 조용히 통과한다.**
#:
#: 이름으로 가르지 않으면 `README.md`가 노트로 잡힌다. 그 파일은 노트를 어떻게
#: 두는지 정하는 규약 문서다.
NOTE_NAME = re.compile(r"^\d+(?:\.\d+){3}$")


def _version_key(name: str) -> tuple[int, ...]:
    """마디를 숫자로 견준다. 글자로 견주면 `5.9`가 `5.10`보다 뒤로 간다."""
    return tuple(int(part) for part in name.split("."))


def note_paths(notes_dir: Path = NOTES_DIR) -> tuple[Path, ...]:
    """판 번호 이름을 가진 노트 전부. 판 순서대로이고, 없으면 빈 튜플이다."""
    found = [p for p in notes_dir.glob("*.md") if NOTE_NAME.match(p.stem)]
    return tuple(sorted(found, key=lambda p: _version_key(p.stem)))


#: 대상별 기본 검사 경로. `doc`은 파일이 여럿이라 여기 없다 - `ko_style`이
#: `USER_DOCS`로 갖고 있고, 그쪽이 목록만 가져다 쓴다.
#:
#: `note`가 지금 빈 튜플인 것은 **첫 판 노트를 아직 안 썼기 때문이다.** 노트가
#: 없을 때 조용히 통과하지 않도록 `main`이 그 사실을 따로 말한다.
DEFAULT_PATHS = {
    "mod": (REPO / "korean" / "strings.json",),
    "note": note_paths(),
}

#: `strings.json`에서 발화 값을 담은 줄. 키가 ASCII라 값과 안 섞인다.
_KO_VALUE = re.compile(r'^\s*"ko"\s*:\s*(.*)$')

#: 인라인 코드. 백틱 안은 실물 문구를 인용하는 자리라 안 본다 - `ko_style`과
#: `notes_check` 둘 다 그렇게 하고 있어서 그대로 맞춘다.
_BACKTICK = re.compile(r"`[^`]*`")


class Entry(NamedTuple):
    """낱말 판정 하나. `good`은 비어 있을 수 있다 - 그러면 지우라는 뜻이다."""

    bad: str
    good: str
    why: str
    when: str

    def instead(self) -> str:
        """대신 쓸 것을 사람이 읽는 꼴로."""
        return f"`{self.good}`" if self.good else "지운다"


def load(path: Path = LEXICON_PATH) -> dict:
    """`lexicon.json` 전체."""
    return json.loads(path.read_text(encoding="utf-8"))


def entries(target: str, path: Path = LEXICON_PATH) -> tuple[Entry, ...]:
    """대상 하나의 판정 목록."""
    if target not in TARGETS:
        raise ValueError(f"모르는 대상이다: {target}. 있는 것은 {', '.join(TARGETS)}")
    found = load(path).get("entries", {}).get(target, [])
    return tuple(
        Entry(
            item.get("bad", ""),
            item.get("good", ""),
            item.get("why", ""),
            item.get("when", ""),
        )
        for item in found
    )


def mapping(target: str, path: Path = LEXICON_PATH) -> dict[str, str]:
    """`{쓰면 안 되는 말: 대신 쓸 것}`. `notes_check`가 옛 상수 자리에 쓴다."""
    return {entry.bad: entry.good for entry in entries(target, path)}


def triples(target: str, path: Path = LEXICON_PATH) -> tuple[tuple[str, str, str], ...]:
    """`(표현, 대신 쓸 것, 왜)`. `ko_style`이 옛 상수 자리에 쓴다."""
    return tuple((entry.bad, entry.good, entry.why) for entry in entries(target, path))


def pattern(bad: str) -> re.Pattern[str]:
    """낱말을 잡는 꼴. **앞에 한글이 붙으면 안 잡는다.**"""
    return re.compile(rf"(?<![가-힣]){re.escape(bad)}")


def check_entries(path: Path = LEXICON_PATH) -> list[str]:
    """목록 자체의 위생. `why`가 비면 다음 사람이 그 줄을 근거 없이 믿는다."""
    data = load(path)
    problems: list[str] = []

    missing = [name for name in TARGETS if name not in data.get("entries", {})]
    if missing:
        problems.append(f"`entries`에 대상이 없다: {', '.join(missing)}")

    for target in TARGETS:
        seen: set[str] = set()
        for entry in entries(target, path):
            where = f"{target}의 `{entry.bad}`"
            if not entry.bad.strip():
                problems.append(f"{target}에 빈 표현이 있다")
                continue
            if not entry.why.strip():
                problems.append(f"{where}에 why가 없다")
            if not entry.when.strip():
                problems.append(f"{where}에 when이 없다")
            if entry.bad in seen:
                problems.append(f"{where}가 두 번 있다")
            seen.add(entry.bad)

    # 기각한 낱말이 목록에도 있으면 둘 중 하나가 거짓말이다.
    for item in data.get("rejected", []):
        bad = item.get("bad", "")
        target = item.get("target", "")
        if not item.get("why", "").strip():
            problems.append(f"rejected의 `{bad}`에 why가 없다")
        if target in TARGETS and bad in mapping(target, path):
            problems.append(
                f"`{bad}`가 {target}의 목록과 rejected에 둘 다 있다. "
                "넣기로 정한 것이면 rejected에서 빼라"
            )

    return problems


def scan(lines: list[str], target: str, label: str, path: Path = LEXICON_PATH) -> list[str]:
    """줄 목록에서 되살아난 판정. **`mod`는 발화 값 줄만 본다.**"""
    found: list[str] = []
    for entry in entries(target, path):
        regex = pattern(entry.bad)
        for number, line in enumerate(lines, 1):
            text = line
            if target == "mod":
                value = _KO_VALUE.match(line)
                if value is None:
                    continue
                text = value.group(1)
            else:
                text = _BACKTICK.sub(" ", text)
            if regex.search(text):
                found.append(
                    f"{label}:{number}\n  `{entry.bad}` -> {entry.instead()}\n  왜: {entry.why}"
                )
    return found


def scan_file(path: Path, target: str, lexicon: Path = LEXICON_PATH) -> list[str]:
    """파일 하나. 경로는 저장소 기준으로 줄여 적는다."""
    try:
        label = str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        label = str(path)
    return scan(path.read_text(encoding="utf-8").splitlines(), target, label, lexicon)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="사용자가 판정한 낱말이 되살아난 자리를 잡는다")
    parser.add_argument("paths", nargs="*", type=Path, help="검사할 파일. 없으면 대상의 기본 경로")
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--lexicon", type=Path, default=LEXICON_PATH)
    args = parser.parse_args(argv)

    problems = check_entries(args.lexicon)
    if problems:
        print("낱말 목록 자체가 규약에 안 맞는다:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    paths = list(args.paths) or list(DEFAULT_PATHS.get(args.target, ()))
    if not paths:
        print(
            f"`{args.target}` 대상의 기본 경로가 없다. 검사할 파일을 인자로 줘라",
            file=sys.stderr,
        )
        return 1

    found: list[str] = []
    for path in paths:
        if not path.is_file():
            print(f"파일이 없다: {path}", file=sys.stderr)
            return 1
        found += scan_file(path, args.target, args.lexicon)

    if found:
        print(f"사용자가 판정한 낱말이 되살아났다 ({args.target}):", file=sys.stderr)
        for item in found:
            print(item, file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "판정이 다투면 korean/lexicon.json을 고쳐라. 그 파일이 근거를 갖는다.",
            file=sys.stderr,
        )
        return 1

    total = len(entries(args.target, args.lexicon))
    print(f"통과 - {args.target} 낱말 {total}개가 파일 {len(paths)}개에서 되살아나지 않았다")
    print("  이 검사는 목록에 있는 낱말만 본다. 문장 품질 전반은 안 본다 -")
    print("  목록은 사용자 교정에서만 자란다(korean/lexicon.json의 `rule`)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
