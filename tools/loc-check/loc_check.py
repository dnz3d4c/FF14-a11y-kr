"""설치 프로그램의 안내 문구가 한국어로 나가는지 지킨다.

## 무엇을 막나

**조용한 영어 폴백.** `Installer/Loc.cs`의 `Get`은 현재 언어에 키가 없으면 영어로
떨어지고(`Loc.cs:29`), 영어에도 없으면 **키 이름을 그대로 돌려준다**. 둘 다 예외도
로그도 안 남긴다. 한국 사용자는 영어 문장을, 최악에는 `InstallerAssetMissing` 같은
식별자를 화면에서 읽게 된다.

새는 자리는 **0건이다**(2026-09-04 실측 - 불리는 키 195개가 전부 한국어를 갖고 있다).
그래서 지금 못박는다. 이 검사가 막는 것은 이미 난 사고가 아니라 **다음에 영어 키만
더하는 순간**이다.

## 왜 조립 산출물을 보나

이 저장소의 설치 프로그램 소스는 세 군데에 흩어져 있다 - `replace/Installer/`가 셋,
`kr/Installer/`가 둘, `upstream/Installer/`가 넷이다. `Loc.Get("키")` 호출은 원본
파일에도 있어서 어느 한 곳만 보면 부르는 키를 다 못 찾는다. **조립 결과가 실제로 나갈
트리이고 판정 대상은 그것이다.** 그래서 `build/Installer`를 본다.

조립을 안 돌렸으면 여기서 멈춘다. 소스가 없으면 부르는 키도 0개가 되어 아래 검사가
전부 조용히 통과하는데, 그 침묵이 통과로 보이면 안 된다.

## 빈 값도 같은 부류다

키가 있어도 값이 비면 `경고: ` 한 줄만 나간다. 실제로 `ConfigNotExist4`가 그
모양이었다. 사전에 자리가 있으니 위의 두 검사는 초록으로 통과한다 - 값까지 봐야
잡힌다.

## `Loc.Get`을 안 거치는 리터럴

`tools/assemble`이 같은 일을 하지만 그쪽이 보는 것은 플러그인(`FF14Accessibility/`)
뿐이고, `Installer/`는 자체 사전이 세 언어를 들고 있어 대장을 안 거친다고 명시적으로
빼 두었다(`tools/assemble/assemble.py:50-52`). **그래서 `Installer/`는 어느 검사에도
안 걸린다.** 여기서 그 자리를 본다 - 사용자에게 나가는 호출(`Info`/`Warn`/`Error`)에
맨 문자열이 들어가거나, 어디든 움라우트를 가진 리터럴이 있으면 잡는다.

## 죽은 키는 골든에 고정한다

영어에만 있고 아무도 안 부르는 키가 28개 있다. 글로벌 설치 프로그램에서 온
`XivLauncher` 잔재라 한국어를 지어낼 이유가 없다. 지우는 것은 원본 소스를 건드리는
일이라 여기서 하지 않고, **늘어나는 것만 막는다.**

사용법:
    uv run python tools/assemble/assemble.py       # 먼저 조립한다
    uv run python tools/loc-check/loc_check.py     # 대조
    uv run python tools/loc-check/loc_check.py --write   # 골든 갱신
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# 주석 지우개는 `tools/assemble`이 갖고 있다 - 같은 일을 두 번 만들지 않는다. 문자열
# 안의 `//`를 주석으로 읽지 않는 것이 여기서도 그대로 필요하다 - 설치 프로그램의 안내
# 문구에 `https://goatcorp.github.io/`가 들어 있다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assemble"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다
import scanner  # noqa: E402 - 위에서 경로를 넣어야 찾는다

SOURCE_ROOT = REPO / "build" / "Installer"
LOC_FILE = SOURCE_ROOT / "Loc.cs"
GOLDEN = Path(__file__).resolve().parent / "golden" / "dead-keys.json"

#: 조립을 안 돌렸을 때 무엇을 하라고 말할지. 메시지를 두 벌로 적지 않는다.
ASSEMBLE = "uv run python tools/assemble/assemble.py"

#: `Loc.cs`가 사전을 다는 이름. 순서는 그 파일이 적은 순서다.
LANGUAGES = ("German", "English", "Korean")

#: 없으면 폴백이 향하는 곳. 여기에도 없으면 키 이름이 그대로 나간다.
FALLBACK = "English"

#: 우리가 사용자에게 보이려는 언어.
TARGET = "Korean"

#: 사람이 듣는 문장을 내보내는 호출. 여기 맨 문자열이 들어가면 그 문장은
#: 어느 언어로도 안 갈린다.
SPEAKING = ("Info", "Warn", "Error")

#: 한국어에도 명령어에도 안 나오는 문자. 원본이 독일어로 개발되기 때문에, 이 글자가
#: 남아 있으면 그 자리는 번역을 안 거친 독일어 문장이다.
UMLAUTS = re.compile(r"[äöüßÄÖÜ]")

#: 글자가 하나도 없는 리터럴은 어느 언어도 아니다. `"  "`(들여쓰기)와
#: `", "`(잇는 조각)가 걸리면 골든이 잡음으로 찬다.
_LETTER = re.compile(r"[^\W\d_]")

#: `string.Format`이 값을 박는 자리. `{{`는 리터럴 중괄호라 자리가 아니다.
_PLACEHOLDER = re.compile(r"\{(\d+)\}")

_ENTRY = re.compile(r'\[\s*"([A-Za-z0-9_]+)"\s*\]\s*=')
_CALL = re.compile(r'Loc\.Get\(\s*"([A-Za-z0-9_]+)"')
_STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"')


@dataclass(frozen=True)
class Bare:
    """`Loc.Get`을 안 거치고 앉아 있는 리터럴 하나."""

    file: str
    rule: str
    text: str
    line: int

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.file, self.rule, self.text)


#: 갈래 이름. 골든에 같이 적어서 왜 잡혔는지가 남는다.
UMLAUT = "umlaut"
SPOKEN = "spoken"


# ---------------------------------------------------------------- 사전 읽기


def _block(text: str, language: str) -> str:
    """`[English] = new Dictionary<string, string> { ... }`의 안쪽.

    중괄호 깊이를 세서 자른다. 값에 `{0}` 같은 서식 자리가 있어서 정규식
    하나로는 끝을 못 찾는다.
    """
    opening = re.search(rf"\[{language}\]\s*=\s*new Dictionary<string, string>\s*\{{", text)
    if opening is None:
        raise ValueError(f"`{language}` 사전을 못 찾았다: {LOC_FILE}")

    start = opening.end()
    depth = 1
    index = start
    while index < len(text) and depth:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1
    return text[start : index - 1]


def dictionaries(path: Path = LOC_FILE) -> dict[str, dict[str, str]]:
    """언어별 (키 -> 값). 값은 이어 붙인 문자열 리터럴들이다.

    값을 이어 붙이는 이유는 긴 문장이 `"앞" +\\n"뒤"`로 나뉘어 있기 때문이다.
    빈 값 판정이 목적이라 서식 자리는 그대로 둔다.
    """
    text = scanner.strip_comments(path.read_text(encoding="utf-8"))
    found: dict[str, dict[str, str]] = {}

    for language in LANGUAGES:
        body = _block(text, language)
        entries: dict[str, str] = {}
        marks = list(_ENTRY.finditer(body))
        for index, mark in enumerate(marks):
            end = marks[index + 1].start() if index + 1 < len(marks) else len(body)
            chunk = body[mark.end() : end]
            entries[mark.group(1)] = "".join(literal[1:-1] for literal in _STRING.findall(chunk))
        found[language] = entries
    return found


def placeholders(value: str) -> frozenset[str]:
    """이 값이 요구하는 서식 자리 번호. `{{`는 리터럴 중괄호라 뺀다."""
    return frozenset(_PLACEHOLDER.findall(value.replace("{{", "").replace("}}", "")))


def called(root: Path = SOURCE_ROOT) -> dict[str, list[str]]:
    """`Loc.Get("키")`로 불리는 키 -> 그 키를 부르는 파일들."""
    calls: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.cs")):
        text = scanner.strip_comments(path.read_text(encoding="utf-8"))
        for match in _CALL.finditer(text):
            calls.setdefault(match.group(1), []).append(path.name)
    return calls


# ------------------------------------------------------- `Loc.Get` 밖 리터럴


def _speaking_call(before: str) -> bool:
    """이 리터럴 바로 앞이 사람에게 말하는 호출의 여는 괄호인가."""
    return any(re.search(rf"(?<![A-Za-z0-9_]){name}\($", before) for name in SPEAKING)


def scan_text(text: str, name: str) -> list[Bare]:
    """한 파일에서 `Loc.Get`을 안 거치는 리터럴을 찾는다."""
    stripped = scanner.strip_comments(text)
    found: list[Bare] = []

    for match in _STRING.finditer(stripped):
        literal = match.group(0)[1:-1]
        if not _LETTER.search(literal):
            continue

        before = stripped[: match.start()].rstrip()
        # `Loc.Get("Key")`의 그 키는 사전을 거치는 정상 경로다.
        if re.search(r"Loc\.Get\($", before):
            continue

        if UMLAUTS.search(literal):
            rule = UMLAUT
        elif _speaking_call(before):
            rule = SPOKEN
        else:
            continue

        found.append(Bare(name, rule, literal, stripped.count("\n", 0, match.start()) + 1))
    return found


def scan_bare(root: Path = SOURCE_ROOT) -> list[Bare]:
    """설치 프로그램 전체. `Loc.cs`는 사전 자신이라 범위 밖이다."""
    found: list[Bare] = []
    for path in sorted(root.rglob("*.cs")):
        if path.name == LOC_FILE.name:
            continue
        found += scan_text(path.read_text(encoding="utf-8"), path.name)
    return found


# ------------------------------------------------------------------- 골든


def load_golden(path: Path = GOLDEN) -> list[str]:
    if not path.is_file():
        return []
    keys: list[str] = json.loads(path.read_text(encoding="utf-8"))["keys"]
    return keys


def dead_keys(entries: dict[str, dict[str, str]], calls: dict[str, list[str]]) -> list[str]:
    """번역이 없는데 아무도 안 부르는 키. 화면에 안 나가므로 결함이 아니다."""
    return sorted(
        key for key in entries[FALLBACK].keys() - entries[TARGET].keys() if key not in calls
    )


def write_golden(keys: list[str], path: Path = GOLDEN) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "note": (
                    "영어 사전에만 있고 아무도 `Loc.Get`으로 안 부르는 키. "
                    "글로벌 설치 프로그램에서 온 `XivLauncher` 잔재라 한국어를 "
                    "지어낼 이유가 없다. 지우는 것은 원본 소스를 건드리는 "
                    "일이라 여기서 안 한다 - 늘어나는 것만 막는다. "
                    "불리기 시작하면 이 목록이 아니라 `번역 없음`으로 걸린다."
                ),
                "keys": sorted(keys),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return len(keys)


# ------------------------------------------------------------------- 검사


def check(root: Path = SOURCE_ROOT, golden_path: Path = GOLDEN) -> list[str]:
    """어긋난 자리. 빈 목록이면 통과다."""
    entries = dictionaries(root / LOC_FILE.name)
    calls = called(root)
    bad: list[str] = []

    # 1) 불리는데 한국어가 없다 -> 조용히 영어가 나간다.
    missing = (k for k in calls if k in entries[FALLBACK] and k not in entries[TARGET])
    for key in sorted(missing):
        bad.append(
            f"{key}: 한국어가 없어 영어로 나간다 "
            f"({', '.join(sorted(set(calls[key])))}). `Loc.cs`의 [Korean]에 넣어라"
        )

    # 2) 불리는데 어느 사전에도 없다 -> 키 이름이 그대로 화면에 나간다.
    for key in sorted(k for k in calls if k not in entries[FALLBACK]):
        bad.append(
            f"{key}: 어느 사전에도 없다 ({', '.join(sorted(set(calls[key])))}). "
            f"`Loc.Get`이 키 이름을 그대로 돌려준다"
        )

    # 3) 값이 비었다 -> 자리는 있는데 아무 말도 안 나간다.
    for language in LANGUAGES:
        for key, value in sorted(entries[language].items()):
            if not value.strip():
                bad.append(f"{key}: [{language}] 값이 비어 있다. 접두만 붙은 빈 줄이 나간다")

    # 4) `Loc.Get`을 안 거치는 리터럴.
    for item in scan_bare(root):
        bad.append(
            f"{item.file}:{item.line}: `Loc.Get` 밖의 리터럴({item.rule}) "
            f"{item.text!r}. 사전에 키를 만들어 거쳐라"
        )

    # 5) 죽은 키가 늘었나.
    now = dead_keys(entries, calls)
    was = load_golden(golden_path)
    added = sorted(set(now) - set(was))
    dropped = sorted(set(was) - set(now))
    if added:
        bad.append(
            f"번역 없는 키가 새로 생겼다: {', '.join(added)}. "
            f"부를 것이면 한국어를 넣고, 잔재면 --write로 골든에 담아라"
        )
    if dropped:
        bad.append(f"골든에만 남은 키가 있다: {', '.join(dropped)}. --write로 갱신해라")

    # 6) 언어마다 서식 자리가 다르다 -> 넘긴 값이 조용히 버려진다.
    #    `KrWaitingForDalamud`가 그랬다 - 한국어에만 `{0}`이 빠져서
    #    `InstallerService`가 넘긴 `15`가 안 박혔고, 사전 셋을 나란히 놓고
    #    보기 전까지 아무도 못 봤다.
    for key in sorted(set().union(*(entries[language] for language in LANGUAGES))):
        spread = {
            language: placeholders(entries[language][key])
            for language in LANGUAGES
            if key in entries[language]
        }
        if len(spread) > 1 and len(set(spread.values())) > 1:
            shown = " / ".join(
                f"[{language}] " + (", ".join(f"{{{mark}}}" for mark in sorted(marks)) or "없음")
                for language, marks in spread.items()
            )
            bad.append(
                f"{key}: 언어마다 서식 자리가 다르다 ({shown}). 빠진 쪽은 넘긴 값이 버려진다"
            )

    return bad


def main(argv: list[str]) -> int:
    console.setup()
    parser = argparse.ArgumentParser(description="설치 프로그램 안내 문구 검사")
    parser.add_argument("--write", action="store_true", help="죽은 키 골든을 다시 쓴다")
    args = parser.parse_args(argv[1:])

    # 조립 산출물이 판정 대상이다. 없는 채로 돌면 부르는 키가 0개라 아래 검사가
    # 전부 통과하므로, 조용한 초록 대신 여기서 멈추고 무엇을 먼저 돌릴지 말한다.
    if not LOC_FILE.is_file():
        print(f"조립 산출물이 없다: {LOC_FILE}", file=sys.stderr)
        print(f"먼저 조립해라: {ASSEMBLE}", file=sys.stderr)
        return 1

    if args.write:
        entries = dictionaries()
        count = write_golden(dead_keys(entries, called()))
        print(f"골든을 다시 썼다 - 번역 없는 죽은 키 {count}개")
        return 0

    bad = check()
    if bad:
        print("설치 프로그램 문구가 한국어로 안 나간다:", file=sys.stderr)
        for item in bad:
            print(f"  {item}", file=sys.stderr)
        return 1

    entries = dictionaries()
    print(
        f"통과 - 부르는 키 {len(called())}개가 전부 한국어를 갖고 있다 "
        f"(한국어 {len(entries[TARGET])} / 영어 {len(entries[FALLBACK])})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
