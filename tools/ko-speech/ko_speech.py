"""`Pick` 밖에서 문장으로 새는 외국어 리터럴을 잡는다.

## 무엇을 막나

**대장을 안 거치는 자리는 검사도 대장도 안 본다.** `Loc.Pick`이
`Korean => ko ?? ReportMissing(...)`이라(`replace/FF14Accessibility/Loc.cs:154-160`)
한국어가 없으면 영어가 나가되 그 자리가 로그에 적히기라도 한다. 그런데 애초에
`Pick`을 안 거치고 맨 리터럴로 박혀 있으면 그 폴백조차 없다 - 독일어가 그대로
나간다.

`tools/assemble`은 표식(`IsGerman`·`De`)과 `Pick(`만 본다. 그래서 표식도
`Pick`도 없이 맨 리터럴로 앉은 자리는 미적용에도 못 읽음에도 안 나타난다.
조립 보고의 숫자가 0이어도 이 부류는 그 숫자 밖에 있다. 여기서 그 다음 층을 본다.

옛 저장소에서 실제로 그랬다. 사용자가 인게임에서
`불멸대 막사 방향 통로, Übergang, 54미터, 왼쪽`을 들었는데, 그 `Übergang`은
소스에 맨 리터럴이라 검사 넷이 하나도 못 잡았다. 같은 부류로
`NavCategory.Fates => "FATEs"`가 있었다 - 형제 열다섯이 전부 `Pick(...)`인데
혼자 맨 리터럴이었다.

## 왜 조립 산출물을 보나

`tools/loc-check`가 `build/Installer`를 보는 것과 같은 까닭이다. 이 저장소의
플러그인 소스는 `upstream/`·`kr/`·`replace/` 세 군데에 흩어져 있고, 조립이
`unnest`로 소스를 펴고 `Pick`을 써 넣은 **뒤**의 트리가 실제로 나갈 것이다.
판정 대상은 그것이다. 조립을 안 돌렸으면 여기서 멈춘다 - 소스가 없으면 0건이
되고, 그 침묵이 통과로 보이면 안 된다.

## 두 갈래로 나눠 본다

한 규칙으로 묶으면 오탐이 섞여 둘 다 죽는다. 그래서 판정을 나눈다.

- **움라우트**(`UMLAUT`) - `[äöüßÄÖÜ]`를 가진 리터럴 중 파서가 잡은 `Pick`/삼항
  안이 아닌 것. 이 문자는 한국어에도 명령어에도 절대 안 나와서 문자셋만으로
  갈린다
- **형제 대조**(`SIBLING`) - `switch` 식이나 배열 초기화 안에서 형제 가지 중
  하나 이상이 `Pick(...)`인데 자기만 맨 문자열 리터럴인 가지. 움라우트가 없는
  `Aethernet`·`Ort`·`FATEs`는 이 규칙으로만 잡힌다

## 오탐 셋 - 전부 계산으로 갈린다

1. **비교 키** - `p.TypeLabel is "Ätheryt" or "Aethernet"`(`PlacesService.cs`).
   발화가 아니라 식별자다. 리터럴만 바꾸면 에테라이트 분류가 예외도 로그도 없이
   죽는다. `is`/`==`/`!=`/`case`/가지 라벨의 피연산자면 통과시킨다
2. **로그** - `_log.Info($"[Nav] ...")`. 사람이 듣는 문장이 아니다. 감싸는 호출
   중 하나라도 `...log`면 통과시킨다
3. **파서가 모양을 못 읽은 언어 분기** - `AccessibilityStrings.cs`의 중첩 삼항.
   조립도 못 읽어 `못 읽음`으로 세는 자리와 같은 부류라, 여기서 다시 세면 상태가
   두 벌이 된다. 그 리터럴이 앉은 문장에 `scanner.MARKERS`의 표식이 있으면
   통과시킨다

옛 저장소에는 넷째가 있었다 - `ColorNamer.cs`가 `De`라는 자기 별칭을 둬서
표식(`IsGerman`)에 안 잡히고 104곳이 영어로 나가던 것이다. **여기서는 없다.**
`scanner.MARKERS`가 `De`를 표식으로 갖고 있어서 조립이 그 104곳을 이미
`Pick(...)`으로 열었다. 그래서 3번 규칙이 표식 목록을 통째로 가져다 쓴다.

## 골든이 판단을 담는다

셋으로 안 갈리는 잔여분을 `golden/speech-sites.json`에 고정하고, 늘면 실패시킨다.
**골든에 넣는 것은 판단이라 `why`가 비어 있으면 검사가 빨개진다** - 다음 사람이
그 줄을 근거 없이 믿는 것을 막는다. `--write`는 기존 `why`를 그대로 옮겨 적고
새 자리만 빈칸으로 남긴다.

튜플 사전 두 파일은 범위 밖이다(`OUT_OF_SCOPE`). `tools/assemble`이
`TUPLE_TABLES`로 건수만 세는 자리고, 여기서 다시 세면 상태가 두 벌이 되고
골든이 안 읽힌다.

사용법:
    uv run python tools/assemble/assemble.py         # 먼저 조립한다
    uv run python tools/ko-speech/ko_speech.py           # 대조
    uv run python tools/ko-speech/ko_speech.py --write   # 골든 갱신
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# 소스를 읽는 장치는 `tools/assemble`이 갖고 있다 - 같은 일을 두 번 만들지 않는다.
# 주석 지우개·리터럴 읽개·자리 찾개가 거기 있고, 조립이 쓰는 것과 같은 걸음이라야
# "조립이 본 자리"와 "여기서 뺀 자리"가 어긋나지 않는다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assemble"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import assemble  # noqa: E402 - 위에서 경로를 넣어야 찾는다
import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다
import scanner  # noqa: E402 - 위에서 경로를 넣어야 찾는다

SOURCE_ROOT = REPO / "build" / assemble.SOURCE_NAME
GOLDEN = Path(__file__).resolve().parent / "golden" / "speech-sites.json"

#: 조립을 안 돌렸을 때 무엇을 하라고 말할지. 메시지를 두 벌로 적지 않는다.
ASSEMBLE = "uv run python tools/assemble/assemble.py"

#: 갈래 이름. 골든에 같이 적어서 왜 잡혔는지가 남는다.
UMLAUT = "umlaut"
SIBLING = "sibling"
SPEECH = "speech"

#: 사용자에게 그대로 나가는 자리. 여기 들어간 리터럴은 문자셋이 무엇이든,
#: 형제가 있든 없든 사람이 한 번 봐야 한다. **한 줄짜리 새 파일이 앞 두
#: 갈래를 통째로 빠져나가는 것**을 막는 자리다 - 움라우트도 형제도 없으면
#: 아무것도 안 물었다. 조회(`WasRecentlySpoken`)와 기록(`RememberSpokenVariant`)은
#: 인자를 받아도 나가는 것이 아니라 뺀다.
SPEECH_SINKS = frozenset({"Speak", "SpeakInterrupt", "Braille"})

#: 보간 자리. 발화되는 실제 글자는 그 안의 **값**이라 여기서 볼 것이 아니다.
#: 안 닫힌 것까지 지운다 - `_split`이 삼항을 자르면 `{(moved.Y > 0 ? `처럼
#: 반쪽이 남는다.
_INTERPOLATION = re.compile(r"\{[^}]*\}?")

#: 한글이 한 자라도 있으면 이미 옮긴 자리다.
_HANGUL = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]")

#: 라틴 글자. 이것이 없으면 구두점과 공백뿐이라 어느 언어도 아니다.
_LATIN = re.compile(r"[A-Za-z]")

#: 한국어에도 명령어에도 안 나오는 문자. 문자셋만으로 독일어가 갈린다.
UMLAUTS = re.compile(r"[äöüßÄÖÜ]")

#: `tools/assemble`이 건수만 세는 튜플 사전. 목록을 여기 베끼면 그쪽이 늘 때
#: 따라오지 못하고, 그러면 같은 파일을 두 도구가 서로 다르게 센다.
OUT_OF_SCOPE = frozenset(assemble.TUPLE_TABLES)

#: 언어 분기의 표식. **조립이 쓰는 목록 그대로다.** 조립이 표식으로 보는 자리는
#: 조립이 열거나 `못 읽음`으로 세므로, 여기서 또 세면 상태가 두 벌이 된다.
#: `Loc.IsKorean`은 `replace/FF14Accessibility/Loc.cs:84`에 선언만 있고 갈림길로
#: 쓰는 자리가 하나도 없어서(2026-09-04 실측) 따로 더하지 않는다.
MARKERS = scanner.MARKERS

#: 표식을 **낱말 하나로** 찾는다. `scanner._standalone`이 조립에서 하는 판정과 같다.
#: 옛 저장소의 표식은 `IsGerman`·`IsKorean`이라 부분 문자열로 찾아도 남의 이름 안에
#: 안 들어갔는데, `De`는 두 글자라 `Destination`·`Detail`의 머리에 그대로 들어 있다.
#: 부분 문자열로 재면 그런 문장에 앉은 리터럴이 통째로 언어 분기로 오해받아 조용히
#: 빠진다. 지금 트리에서는 두 판정의 결과가 43건으로 같지만(2026-09-04 실측),
#: 같은 것은 이번 트리뿐이라 여기서 막아 둔다.
#:
#: `.` 뒤는 막되 `Loc.` 한정자만 통과시킨다 - `t.De`는 튜플 필드라 표식이 아니고,
#: `.` 뒤를 통째로 막으면 `Loc.IsGerman`을 쓰는 파일이 안 잡힌다.
_MARKER = re.compile(
    r"(?:(?<=Loc\.)|(?<![A-Za-z0-9_.]))"
    + r"(?:"
    + "|".join(re.escape(marker) for marker in MARKERS)
    + r")"
    + r"(?![A-Za-z0-9_])"
)

#: 비교 피연산자. 앞에 오는 것과 뒤에 오는 것을 따로 본다.
_BEFORE = re.compile(r"(?:^|[^A-Za-z0-9_])(is|or|and|case|==|!=)\s*$")
_AFTER = re.compile(r"^\s*(=>|==|!=|(?:or|and)(?![A-Za-z0-9_]))")

#: 글자가 하나도 없는 리터럴은 어느 언어도 아니다. `""`(일부러 아무 말도 안 하는
#: 가지)와 `", "`(잇는 조각)가 형제 대조에 걸리면 골든이 잡음으로 찬다.
_LETTER = re.compile(r"[^\W\d_]")

_PICK = re.compile(r"(?<![A-Za-z0-9_])Pick\s*\(")
_CHAIN = re.compile(r"[A-Za-z0-9_.]+$")

#: 문자열 속을 가려 둘 때 쓰는 글자. 원문에 안 나오는 것이면 아무거나 된다.
_MASK = "\x01"


@dataclass(frozen=True)
class Literal:
    """소스에 앉아 있는 문자열 리터럴 하나. 자리는 원문 기준이다."""

    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Finding:
    file: str
    rule: str
    text: str
    line: int

    @property
    def key(self) -> tuple[str, str, str]:
        """골든이 쓰는 이름표. **줄 번호를 안 넣는다** - 무관한 편집마다 골든이
        흔들리면 아무도 안 본다. `tools/loc-check`의 골든과 같은 규약이다."""
        return (self.file, self.rule, self.text)


# --- 소스를 읽는 최소 장치 -------------------------------------------------


def literals(stripped: str) -> list[Literal]:
    """문자열 리터럴을 전부 뽑는다. 축자 문자열(`@"..."`)은 못 읽고 넘어간다."""
    found: list[Literal] = []
    i, n = 0, len(stripped)
    while i < n:
        if stripped[i] == '"' or (stripped[i] == "$" and stripped[i + 1 : i + 2] == '"'):
            text, start, end = scanner.read_literal(stripped, i)
            if text is not None:
                found.append(Literal(text, start, end))
                i = end
                continue
        i += 1
    return found


def mask(stripped: str, found: list[Literal]) -> str:
    """리터럴 속을 가린 사본. 길이는 그대로라 자리가 원문과 1대1로 맞는다.

    괄호 깊이를 세는 데 쓴다. 안 가리면 `$"{a}, {b}"` 안의 중괄호와 쉼표가
    구조로 읽혀서 형제 대조가 통째로 어긋난다.
    """
    out = list(stripped)
    for item in found:
        out[item.start : item.end] = _MASK * (item.end - item.start)
    return "".join(out)


def _statement(masked: str, position: int) -> str:
    """리터럴이 앉은 문장. 앞뒤로 가장 가까운 `;`·`{`·`}` 사이다.

    C# 문법을 다 읽지 않고도 "이 리터럴이 언어 분기 안에 있나"를 물을 수 있으면
    충분하다. 넓게 잡히는 쪽이 안전하다 - 좁게 잡아 놓치면 오탐이 골든을 채운다.
    """
    start = max(masked.rfind(ch, 0, position) for ch in ";{}") + 1
    ends = [pos for pos in (masked.find(ch, position) for ch in ";{}") if pos >= 0]
    return masked[start : min(ends) if ends else len(masked)]


def _is_comparison(masked: str, item: Literal) -> bool:
    """비교 키인가. `is`/`==`/`!=`/`case`와 `switch` 가지 라벨을 본다."""
    return bool(_BEFORE.search(masked[: item.start]) or _AFTER.match(masked[item.end :]))


def _enclosing_call(masked: str, position: int) -> tuple[str, int] | None:
    """감싸는 호출의 이름과 여는 괄호 자리. 인자가 아니면 None."""
    depth = 0
    i = position - 1
    while i >= 0:
        ch = masked[i]
        if ch in ")]}":
            depth += 1
        elif ch in "([{":
            if depth > 0:
                depth -= 1
            elif ch == "(":
                chain = _CHAIN.search(masked[:i])
                return (chain.group(0) if chain else "", i)
            else:
                return None  # 배열·블록 안이다. 호출 인자가 아니다
        elif ch == ";":
            return None
        i -= 1
    return None


def _in_log(masked: str, item: Literal) -> bool:
    """로그 인자인가. 감싸는 호출을 바깥으로 훑는다.

    `_log.Info(string.Join(", ", parts))`처럼 한 겹 더 들어가 있어도 잡아야
    해서, 가장 안쪽 호출만 보지 않는다.
    """
    position = item.start
    while (call := _enclosing_call(masked, position)) is not None:
        name, opening = call
        if any(part.lstrip("_").lower() == "log" for part in name.split(".")):
            return True
        position = opening
    return False


def _reads_as_foreign(text: str) -> bool:
    """보간을 걷어낸 나머지가 외국어 문장인가.

    발화되는 실제 글자는 보간 **값**이라 `{name}.`이나 `{head}, {text}`는
    이 도구가 볼 것이 아니다 - 걷어내면 구두점만 남는다. 한글이 한 자라도
    있으면 이미 옮긴 자리다.
    """
    rest = _INTERPOLATION.sub("", text)
    return bool(_LATIN.search(rest)) and not _HANGUL.search(rest)


def _in_speech(masked: str, item: Literal) -> bool:
    """발화 싱크의 인자인가. 감싸는 호출을 바깥으로 훑는다.

    `_tolk.Speak(string.Format("...", x))`처럼 한 겹 더 들어가 있어도 잡아야
    해서 가장 안쪽 호출만 보지 않는다. `_in_log`와 같은 걸음이다.
    """
    position = item.start
    while (call := _enclosing_call(masked, position)) is not None:
        name, opening = call
        if name.split(".")[-1] in SPEECH_SINKS:
            return True
        position = opening
    return False


def _excused(masked: str, item: Literal) -> bool:
    """오탐 셋 - 비교 키, 로그, 파서가 못 읽은 언어 분기."""
    if _is_comparison(masked, item):
        return True
    if _in_log(masked, item):
        return True
    return bool(_MARKER.search(_statement(masked, item.start)))


# --- 형제 대조 -------------------------------------------------------------


def _split(masked: str, start: int, end: int) -> list[tuple[int, int]]:
    """깊이 0의 쉼표로 자른다. 괄호·중괄호·대괄호 안의 쉼표는 안 센다."""
    parts: list[tuple[int, int]] = []
    depth, left = 0, start
    for i in range(start, end):
        ch = masked[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append((left, i))
            left = i + 1
    parts.append((left, end))
    return parts


def _groups(masked: str) -> list[tuple[int, int]]:
    """형제가 나란히 앉는 자리 - `{...}`와 `[...]`의 속. 괄호는 안 센다."""
    found: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    for i, ch in enumerate(masked):
        if ch in "([{":
            stack.append((ch, i))
        elif ch in ")]}":
            if not stack:
                continue
            opening, position = stack.pop()
            if opening in "{[":
                found.append((position + 1, i))
    return found


def _value(masked: str, start: int, end: int) -> tuple[int, int]:
    """가지의 값. `A => expr`이면 화살표 뒤, 아니면 통째로."""
    depth = 0
    cut = start
    for i in range(start, end - 1):
        ch = masked[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0 and masked[i : i + 2] == "=>":
            cut = i + 2
    return (cut, end)


def _trim(masked: str, start: int, end: int) -> tuple[int, int]:
    while start < end and masked[start] in " \t\r\n":
        start += 1
    while end > start and masked[end - 1] in " \t\r\n":
        end -= 1
    return (start, end)


def _sibling_literals(masked: str, found: list[Literal]) -> set[int]:
    """형제 중 하나 이상이 `Pick`인데 자기만 맨 리터럴인 가지. 그 자리들."""
    spans = {(item.start, item.end): item for item in found}
    flagged: set[int] = set()

    for group_start, group_end in _groups(masked):
        bare: list[Literal] = []
        picked = False
        for part_start, part_end in _split(masked, group_start, group_end):
            span = _trim(masked, *_value(masked, part_start, part_end))
            if span[0] >= span[1]:
                continue
            if _PICK.search(masked[span[0] : span[1]]):
                picked = True
            elif span in spans:
                bare.append(spans[span])
        if picked:
            flagged |= {item.start for item in bare}
    return flagged


# --- 훑기 ------------------------------------------------------------------


def scan_text(text: str, name: str) -> list[Finding]:
    """한 파일에서 새는 자리를 뽑는다.

    주석은 같은 길이의 공백으로 지우고 본다 - 주석에 적은 예시를 코드로 읽으면
    개수가 가짜로 늘어 진짜 증가를 못 본다.
    """
    stripped = scanner.strip_comments(text)
    found = literals(stripped)
    masked = mask(stripped, found)

    inside = [(site.start, site.end) for site in scanner.find_sites(text)]
    siblings = _sibling_literals(masked, found)

    findings: list[Finding] = []
    for item in found:
        if not _LETTER.search(item.text):
            continue
        if any(a <= item.start and item.end <= b for a, b in inside):
            continue
        if _excused(masked, item):
            continue

        if UMLAUTS.search(item.text):
            rule = UMLAUT
        elif item.start in siblings:
            rule = SIBLING
        elif _in_speech(masked, item) and _reads_as_foreign(item.text):
            rule = SPEECH
        else:
            continue

        findings.append(Finding(name, rule, item.text, stripped.count("\n", 0, item.start) + 1))
    return findings


def scan(root: Path = SOURCE_ROOT) -> list[Finding]:
    """조립이 끝난 소스 전체. 범위 밖 파일은 안 연다."""
    findings: list[Finding] = []
    for path in assemble.source_files(root):
        name = path.relative_to(root).as_posix()
        if name in OUT_OF_SCOPE:
            continue
        findings += scan_text(path.read_text(encoding="utf-8"), name)
    return findings


# --- 골든 ------------------------------------------------------------------


def load_golden(path: Path = GOLDEN) -> list[dict]:
    if not path.is_file():
        return []
    sites: list[dict] = json.loads(path.read_text(encoding="utf-8"))["sites"]
    return sites


def _keys(findings: list[Finding]) -> list[tuple[str, str, str]]:
    return sorted({finding.key for finding in findings})


def compare(
    findings: list[Finding], golden: list[dict]
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """(새로 들어온 것, 골든에만 남은 것)."""
    now = set(_keys(findings))
    was = {(site["file"], site["rule"], site["text"]) for site in golden}
    return (sorted(now - was), sorted(was - now))


def write_golden(findings: list[Finding], path: Path = GOLDEN) -> int:
    """골든을 다시 쓴다. **기존 `why`는 그대로 옮겨 적는다** - 사람이 쓴 판단을
    갱신 한 번에 날리면 아무도 다시 안 적는다."""
    reasons = {
        (site["file"], site["rule"], site["text"]): site.get("why", "")
        for site in load_golden(path)
    }
    sites = [
        {
            "file": file,
            "rule": rule,
            "text": text,
            "why": reasons.get((file, rule, text), ""),
        }
        for file, rule, text in _keys(findings)
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "note": "`Pick` 밖에 맨몸으로 있는 외국어 리터럴 중, 계산으로 안 "
                "갈리는 잔여분. 통과시킬 것도 아직 못 고친 결함도 여기 "
                "모인다 - 어느 쪽인지는 `why`가 말한다.",
                "source": f"build/{assemble.SOURCE_NAME} (조립 산출물)",
                "rules": {
                    UMLAUT: "움라우트를 가진 리터럴이 Pick 밖에 있다",
                    SIBLING: "형제 가지가 Pick인데 자기만 맨 리터럴이다",
                    SPEECH: "발화 싱크에 바로 들어가는데 한글이 없다",
                },
                "sites": sites,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return len(sites)


def main(argv: list[str]) -> int:
    console.setup()

    # 조립 산출물이 판정 대상이다. 없는 채로 돌면 0건이 나오는데, 그 침묵은
    # "새는 자리가 없다"와 구분이 안 된다. 그래서 멈추고 무엇을 먼저 돌릴지 말한다.
    if not SOURCE_ROOT.is_dir():
        print(f"조립 산출물이 없다: {SOURCE_ROOT}", file=sys.stderr)
        print(f"먼저 조립해라: {ASSEMBLE}", file=sys.stderr)
        return 1

    findings = scan()

    if "--write" in argv:
        print(f"골든 갱신: {write_golden(findings)}개")
        빈칸 = [site for site in load_golden() if not site.get("why", "").strip()]
        if 빈칸:
            print(f"\n왜 통과시키는지 안 적힌 자리 {len(빈칸)}개 - 채워라:", file=sys.stderr)
            for site in 빈칸:
                print(f"  {site['file']}  {site['rule']}  {site['text'][:60]}", file=sys.stderr)
            return 1
        return 0

    golden = load_golden()
    if not golden:
        print(f"골든이 없다 - --write로 만든다: {GOLDEN}", file=sys.stderr)
        return 1

    빈칸 = [site for site in golden if not site.get("why", "").strip()]
    added, dropped = compare(findings, golden)
    if not (added or dropped or 빈칸):
        print(f"통과 - 새는 자리 {len(_keys(findings))}개, 골든 그대로")
        return 0

    print("골든과 다르다:", file=sys.stderr)
    for file, rule, text in added:
        print(f"  + {file}  [{rule}]  {text[:60]}  (발화에 외국어가 새로 샌다)", file=sys.stderr)
    for file, rule, text in dropped:
        print(
            f"  - {file}  [{rule}]  {text[:60]}  (이제 없다 - --write로 갱신해라)", file=sys.stderr
        )
    for site in 빈칸:
        print(
            f"  ? {site['file']}  [{site['rule']}]  {site['text'][:60]}  "
            "(왜 통과시키는지 안 적혀 있다)",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
