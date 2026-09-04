"""C# 소스에서 한 문장이 앉은 자리를 읽고, 대장대로 다시 쓴다.

## 무엇을 건드리고 무엇을 안 건드리나

건드리는 자리는 **대장에 있는 쌍뿐이다.** 이것이 이중 안전장치다. 파서가 못 읽는
모양(중첩 삼항, 이어붙이기, 배열)은 애초에 안 잡히고, 잡히더라도 대장에 없으면
안 건드린다. 잘못 읽어 조각난 문자열도 대장에 있을 리 없다.

독일어와 영어 리터럴은 **읽기만 한다.** 원문을 그대로 되쓰고 세 번째 인자를 붙일
뿐이라, 독일어와 영어 사용자가 듣는 문장은 조립 전후로 같아야 한다.

## 표식으로 못 보는 것

갈림길을 알아보는 표식은 `IsGerman`과 `Pick` 둘뿐이다. 별칭을 따로 정의하고 그
별칭으로 갈라지는 자리(`ColorNamer.cs`의 `De`)는 여기서 한 건도 안 잡힌다.
그러므로 미적용 0건은 "다 옮겼다"가 아니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: 갈림길을 알아보는 표식.
MARKER = "IsGerman"
PICK = "Pick("

#: 한 줄이 이 칸을 넘으면 인자마다 줄을 나눈다. 원본 소스의 폭에 맞췄다.
WIDTH = 100

#: 멤버 선언의 이름. `[CallerMemberName]`이 런타임에 넘기는 것과 같은 이름을
#: 정적으로 뽑기 위한 것이라, 보고의 이름과 로그의 이름이 서로 맞는다.
MEMBER = re.compile(
    r"^[ \t]*(?:public|private|internal|protected)[^\n=(){}]*?\b(\w+)\s*(?:=>|\(|=)", re.M
)

_IDENT = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
_NEWLINE = chr(10)


@dataclass(frozen=True)
class Site:
    """소스에서 한 문장이 앉아 있는 자리."""

    start: int
    end: int
    de: str
    en: str
    de_raw: str
    en_raw: str
    #: 이미 소스에 박혀 있는 한국어. 세 인자짜리 `Pick`에만 있다.
    ko: str | None
    line: int
    #: `Loc.` 또는 빈 문자열. 그 자리가 쓰던 표기를 그대로 되쓴다.
    qualifier: str = ""
    #: 아직 안 옮긴 `IsGerman ? de : en`인가. 이미 `Pick(...)`인 자리와 가른다.
    ternary: bool = False


@dataclass
class Result:
    """소스 한 파일을 다시 쓴 결과."""

    text: str
    #: 실제로 한국어를 써 넣은 자리. 같은 쌍이 여러 자리에 있으면 여러 번 들어간다.
    applied: list[tuple[str, str]] = field(default_factory=list)
    #: 소스에서 만난 모든 쌍. 고아를 계산하는 쪽이 쓴다.
    seen: list[tuple[str, str]] = field(default_factory=list)
    #: 보간 자리가 안 맞아 한국어 없이 내보낸 자리.
    bad_slots: list[str] = field(default_factory=list)
    #: 갈림길인 것은 알겠는데 못 읽은 자리의 행 번호.
    unreadable: list[int] = field(default_factory=list)


def strip_comments(text: str) -> str:
    """주석을 같은 길이의 공백으로 지운다.

    주석에 `IsGerman ? de : en` 같은 예시를 적어 두면 파서가 그것을 코드로 읽는다.
    길이를 유지하는 이유는 줄 번호와 위치가 원문과 1대1로 맞아야 해서다. 문자열 안의
    `//`(URL 같은 것)는 주석이 아니므로 문자열도 같이 따라가며 읽는다.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            # 문자열은 통째로 건너뛴다. 안에 //가 있어도 주석이 아니다.
            i += 1
            while i < n:
                if text[i] == chr(92) and i + 1 < n:
                    i += 2
                    continue
                if text[i] == '"' or text[i] == _NEWLINE:
                    i += 1
                    break
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != _NEWLINE:
                out[i] = " "
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                if text[i] != _NEWLINE:
                    out[i] = " "
                i += 1
            for _ in range(2):
                if i < n:
                    out[i] = " "
                    i += 1
            continue
        i += 1
    return "".join(out)


def read_literal(text: str, i: int) -> tuple[str | None, int, int]:
    """C# 문자열 리터럴을 읽는다. (내용, 시작, 끝).

    시작은 `$` 접두를 포함한다. 원문을 그대로 되쓰기 위해서다. 축자 문자열(`@"..."`)은
    이스케이프 규칙이 달라서 읽지 않는다.

    ## 중괄호 깊이는 보간 리터럴에서만 센다

    보간 자리(`{...}`) 안은 식이라 그 안의 문자열이 escape 없이 그대로 들어간다.
    깊이를 안 세면 `$"{(on ? "an" : "aus")}"`의 `"an` 앞 따옴표를 리터럴의 끝으로
    오해한다. 반대로 `$`가 없는 리터럴에서 깊이를 세면 내용에 짝 없이 들어 있는 `{`
    하나가 닫는 따옴표를 삼켜, 멀쩡히 읽히던 자리를 잃는다. 그래서 `$` 접두를 봤을
    때만 센다.
    """
    raw_start = i
    interpolated = i < len(text) and text[i] == "$"
    if interpolated:
        i += 1
    if i >= len(text) or text[i] != '"':
        return None, raw_start, i
    if i > 0 and text[i - 1] == "@":
        return None, raw_start, i

    i += 1
    out: list[str] = []
    depth = 0
    while i < len(text):
        ch = text[i]
        if ch == chr(92) and i + 1 < len(text):
            out.append(text[i : i + 2])
            i += 2
            continue
        # `{{`와 `}}`는 중괄호 글자 자체다. 자리가 아니라 깊이를 세지 않는다.
        if interpolated and ch == "{" and text[i + 1 : i + 2] == "{":
            out.append(text[i : i + 2])
            i += 2
            continue
        if interpolated and ch == "}" and depth == 0 and text[i + 1 : i + 2] == "}":
            out.append(text[i : i + 2])
            i += 2
            continue
        if interpolated and ch == "{":
            depth += 1
        elif interpolated and ch == "}":
            depth = max(0, depth - 1)
        elif ch == '"':
            if depth == 0:
                return "".join(out), raw_start, i + 1
            # 보간 자리 안의 문자열이다. 통째로 삼킨다. 앞 글자가 `$`이면 그 자리에서
            # 부른다. 안쪽이 또 보간일 수 있고, 그때 안쪽에서도 깊이를 세야 한다.
            nested_at = i - 1 if text[i - 1] == "$" else i
            nested, _, nested_end = read_literal(text, nested_at)
            if nested is None:
                return None, raw_start, nested_end
            # `$`는 앞 회차에서 이미 넣었으므로 지금 자리부터 자른다.
            out.append(text[i:nested_end])
            i = nested_end
            continue
        elif ch == _NEWLINE:
            return None, raw_start, i
        out.append(ch)
        i += 1
    return None, raw_start, i


def _skip(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    return i


def _qualified(text: str, found: int) -> tuple[int, str]:
    """`Loc.`이 앞에 붙어 있으면 자리를 그만큼 앞으로 물리고 표기를 돌려준다.

    파일마다 관례가 다르다. `AccessibilityStrings.cs`는 축약 `IsGerman`을 두고 쓰고,
    다른 파일은 `Loc.IsGerman`을 그대로 쓴다. 한쪽으로 통일하면 그 파일이 안 쓰던
    표기가 섞여 들어간다.
    """
    prefix = "Loc."
    if text[max(0, found - len(prefix)) : found] == prefix:
        return found - len(prefix), prefix
    return found, ""


def scan(text: str) -> tuple[list[Site], list[int]]:
    """소스를 훑는다. (고칠 수 있는 자리, 갈림길인데 못 읽은 곳의 행 번호).

    못 읽은 곳도 같이 돌려주는 까닭은 **못 읽으면 못 세기** 때문이다. 중첩 삼항이나
    이어붙이기처럼 이 파서가 못 다루는 모양은 자리 목록에 아예 안 들어오므로,
    미적용 개수만 보면 그런 자리가 조용히 늘어도 신호가 없다. 개수를 따로 내면
    도구가 자기 사각지대의 크기를 스스로 말한다.
    """
    stripped = strip_comments(text)
    unreadable: list[int] = []
    sites = [*_ternary_sites(stripped, text, unreadable), *_pick_sites(stripped, text)]
    return sorted(sites, key=lambda site: site.start), sorted(unreadable)


def find_sites(text: str) -> list[Site]:
    """소스에서 고칠 수 있는 자리를 위치와 함께 뽑는다."""
    return scan(text)[0]


def _ternary_sites(stripped: str, text: str, unreadable: list[int]) -> list[Site]:
    """아직 안 옮긴 `IsGerman ? de : en`.

    `?`까지 왔는데 양쪽을 리터럴로 못 읽으면 갈림길이긴 한데 이 파서의 손 밖이다.
    그 행 번호를 `unreadable`에 남긴다.
    """
    sites: list[Site] = []
    start = 0
    while True:
        found = stripped.find(MARKER, start)
        if found < 0:
            return sites
        start = found + len(MARKER)

        i = _skip(stripped, start)
        if i >= len(stripped) or stripped[i] != "?":
            continue  # 갈림길이 아니다. 선언이거나 다른 쓰임이다

        line = stripped.count(_NEWLINE, 0, found) + 1

        i = _skip(stripped, i + 1)
        de, de_start, i = read_literal(stripped, i)
        if de is None:
            unreadable.append(line)
            continue
        de_end = i

        i = _skip(stripped, i)
        if i >= len(stripped) or stripped[i] != ":":
            unreadable.append(line)
            continue

        i = _skip(stripped, i + 1)
        en, en_start, i = read_literal(stripped, i)
        if en is None:
            unreadable.append(line)
            continue

        span, qualifier = _qualified(stripped, found)
        sites.append(
            Site(
                start=span,
                end=i,
                de=de,
                en=en,
                de_raw=text[de_start:de_end],
                en_raw=text[en_start:i],
                ko=None,
                line=line,
                qualifier=qualifier,
                ternary=True,
            )
        )


def _pick_sites(stripped: str, text: str) -> list[Site]:
    """이미 옮긴 `Pick(de, en[, ko])`."""
    sites: list[Site] = []
    start = 0
    while True:
        found = stripped.find(PICK, start)
        if found < 0:
            return sites
        start = found + len(PICK)

        # `PickItem(` 같은 다른 이름을 거른다.
        if found > 0 and stripped[found - 1] in _IDENT:
            continue

        i = _skip(stripped, start)
        de, de_start, i = read_literal(stripped, i)
        if de is None:
            continue  # 선언(`Pick(string de, ...)`)이거나 우리 것이 아니다
        de_end = i

        i = _skip(stripped, i)
        if i >= len(stripped) or stripped[i] != ",":
            continue

        i = _skip(stripped, i + 1)
        en, en_start, i = read_literal(stripped, i)
        if en is None:
            continue
        en_end = i

        ko: str | None = None
        i = _skip(stripped, i)
        if i < len(stripped) and stripped[i] == ",":
            i = _skip(stripped, i + 1)
            ko, _, i = read_literal(stripped, i)
            if ko is None:
                continue
            i = _skip(stripped, i)

        if i >= len(stripped) or stripped[i] != ")":
            continue

        span, qualifier = _qualified(stripped, found)
        sites.append(
            Site(
                start=span,
                end=i + 1,
                de=de,
                en=en,
                de_raw=text[de_start:de_end],
                en_raw=text[en_start:en_end],
                ko=ko,
                line=stripped.count(_NEWLINE, 0, found) + 1,
                qualifier=qualifier,
            )
        )


def member_name(text: str, offset: int) -> str:
    """그 자리를 감싸는 멤버의 이름. 못 찾으면 빈 문자열.

    모드가 로그에 적는 이름은 `[CallerMemberName]`이 채우는 것이고, 여기서 뽑는
    이름은 그것과 같은 자리를 가리킨다. 보고를 읽는 사람이 로그와 대조할 수 있다.
    """
    name = ""
    for match in MEMBER.finditer(text):
        if match.start() >= offset:
            break
        name = match.group(1)
    return name


def _hole_spans(text: str) -> tuple[list[tuple[int, int]], str | None]:
    """최상위 보간 자리의 (내용 시작, 내용 끝) 목록과, 모양이 깨졌으면 그 까닭.

    자리를 정규식으로 잡으면 중첩된 자리를 못 읽는다. `[^{}]+`는 안쪽 `{location}`만
    잡고 그것을 감싼 바깥 자리를 통째로 놓친다. 그래서 중괄호 깊이를 센다.

    자리 안의 문자열 리터럴은 통째로 건너뛴다. 자리 안은 식이라 그 안의 문자열에 든
    중괄호가 깊이를 흔들면 안 된다. `{{`와 `}}`는 자리가 아니라 중괄호 글자다.

    까닭을 같이 돌려주는 것은 세는 쪽과 검사하는 쪽이 **같은 걸음**을 걷게 하기
    위해서다. 검사기가 따로 걸으면 둘이 다르게 읽는 값이 생기고, 그때 검사를 통과한
    값이 조립에서 다르게 잘린다.
    """
    spans: list[tuple[int, int]] = []
    i, depth, start = 0, 0, 0
    while i < len(text):
        ch = text[i]
        if depth == 0 and ch in "{}" and text[i + 1 : i + 2] == ch:
            i += 2  # `{{`와 `}}`는 중괄호 글자 자체다
            continue
        if ch == "{":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "}":
            if depth == 0:
                return spans, "닫는 중괄호가 짝 없이 있다"
            depth -= 1
            if depth == 0:
                spans.append((start, i))
        elif depth > 0 and ch == '"':
            # 앞 글자가 `$`이면 그 자리에서 부른다. 안쪽이 또 보간일 수 있다.
            at = i - 1 if text[i - 1] == "$" else i
            value, _, end = read_literal(text, at)
            if value is None:
                return spans, "보간 자리 안의 따옴표가 안 닫혔다"
            i = end
            continue
        i += 1
    if depth > 0:
        return spans, "여는 중괄호가 안 닫혔다"
    return spans, None


def holes(text: str) -> list[str]:
    """보간 문자열에서 최상위 자리들의 내용을 순서대로."""
    return [text[start:end] for start, end in _hole_spans(text)[0]]


def references(text: str) -> set[str]:
    """자리마다 **문자열 리터럴을 걷어낸 나머지**의 집합.

    대장의 한국어가 그 자리에서 실제로 컴파일되는지 대조하는 열쇠다. 집합이라 순서를
    안 보는데, 그래야 `{index} of {count}`를 `{count}개 중 {index}번째`로 옮길 수
    있다. 한국어는 어순이 달라서 자리를 그대로 두면 말이 안 된다.

    리터럴을 걷어내는 까닭은 **자리 안의 문장도 사용자가 듣는 말**이라서다. 걷어내지
    않으면 `{(on ? "on" : "off")}`를 옮기는 순간 대조가 거부한다.

    서식 지정자는 남긴다. `{distance:F0}`를 `{distance}`로 적으면 소수 자릿수가
    달라진 채로 나가는데, 그것은 걸려야 한다.
    """
    return {_reference(hole) for hole in holes(text)}


def _reference(hole: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(hole):
        if hole[i] == '"' or (hole[i] == "$" and hole[i + 1 : i + 2] == '"'):
            _, _, end = read_literal(hole, i)
            i = max(end, i + 1)
            continue
        out.append(hole[i])
        i += 1
    # 연속 공백을 하나로. 자리 안의 띄어쓰기가 달라진 것을 다른 자리로 세지 않는다.
    return " ".join("".join(out).split())


def body_fault(ko: str) -> str | None:
    """대장의 값 자체가 깨진 모양이면 까닭을, 멀쩡하면 None.

    이번 단계가 지는 새 위험이 여기 있다. 지금까지 대장의 값은 컴파일을 깨뜨릴 수
    없었는데, 자리 안에 escape 안 된 따옴표가 들어가면서 깨뜨릴 수 있게 됐다. 짝이 안
    맞는 중괄호는 C#이 거부하고, 자리 안에서 안 닫힌 따옴표는 뒤따르는 코드를 통째로
    문자열로 만든다.
    """
    return _hole_spans(ko)[1]


def outside_holes(text: str) -> str:
    """보간 자리의 **내용**을 같은 길이의 공백으로 지운다.

    리터럴 규약을 보는 쪽이 자리 안까지 같은 잣대로 보면 멀쩡한 값을 거부한다. 자리
    안은 식이라 따옴표가 escape 없이 들어가기 때문이다. 길이를 유지하는 이유는 남은
    글자의 위치가 원문과 1대1로 맞아야 해서다.
    """
    out = list(text)
    for start, end in _hole_spans(text)[0]:
        out[start:end] = " " * (end - start)
    return "".join(out)


def _literal(ko: str) -> str:
    """한국어를 C# 리터럴로. 보간 자리가 있으면 `$`를 붙인다."""
    return ('$"' if holes(ko) else '"') + ko + '"'


def _render(site: Site, ko: str | None, text: str) -> str:
    """`Pick(...)` 호출을 만든다. 길면 여는 괄호에 맞춰 줄을 나눈다.

    `ko`가 없으면 인자가 둘이다. 그러면 `Loc.Pick`의 `ko`가 null이라 영어가 나가고,
    나가는 길에 그 자리가 로그에 적힌다.
    """
    args = [site.de_raw, site.en_raw]
    if ko is not None:
        args.append(_literal(ko))
    head = site.qualifier + PICK
    column = site.start - text.rfind(_NEWLINE, 0, site.start) - 1

    single = f"{head}{', '.join(args)})"
    if column + len(single) <= WIDTH:
        return single

    pad = " " * (column + len(head))
    return head + f",{_NEWLINE}{pad}".join(args) + ")"


def rewrite(text: str, catalog: dict[tuple[str, str], str]) -> Result:
    """소스 한 파일을 대장대로 다시 쓴다.

    ## 대장에 없는 자리도 `Pick`으로 바꾼다

    안 옮긴 문장은 영어로 나가야 한다. 그런데 삼항을 그대로 두면 그 자리는 `Loc.Pick`을
    아예 안 타므로 모드가 **자기가 영어를 낸 것을 모른다.** 보이지 않는 사용자는 "아직
    번역 안 됨"과 "모드가 죽음"을 못 가르는데, 조립 시점의 집계는 그 사람에게 안 보인다.

    그래서 인자 둘짜리 `Pick(de, en)`으로 바꾼다. `ko`가 null이라 영어가 나가고, 나가는
    길에 그 자리가 로그에 적힌다. 독일어와 영어가 듣는 것은 한 자도 안 달라진다.

    바꾸는 것은 **읽어낸 자리뿐이다.** 못 읽은 모양은 자리 목록에 없으므로 손대지 않고,
    개수만 `unreadable`로 나간다.
    """
    result = Result(text=text)
    edits: list[tuple[int, int, str]] = []

    sites, result.unreadable = scan(text)
    for site in sites:
        key = (site.de, site.en)
        result.seen.append(key)

        wanted = catalog.get(key)
        if wanted is not None:
            missing = sorted(references(site.en) - references(wanted))
            extra = sorted(references(wanted) - references(site.en))
            if missing or extra:
                result.bad_slots.append(
                    f"{site.line}행: 보간 자리가 안 맞아 한국어를 안 넣는다 - "
                    f"한국어에 빠진 것 {missing}, 영어에 없는 것 {extra}"
                )
                wanted = None

        if wanted is None:
            if site.ternary:
                edits.append((site.start, site.end, _render(site, None, text)))
            continue

        # 삼항 자리는 `ko`가 늘 None이라 여기 안 걸린다. 이미 같은 값이 박힌
        # `Pick(de, en, ko)`만 건너뛴다.
        if site.ko == wanted:
            continue

        edits.append((site.start, site.end, _render(site, wanted, text)))
        result.applied.append(key)

    # 뒤에서부터 갈아 끼운다. 앞을 먼저 고치면 뒤쪽 위치가 밀린다.
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]

    result.text = text
    return result
