"""C# 소스에서 한 문장이 앉은 자리를 읽고, 대장대로 다시 쓴다.

## 무엇을 건드리고 무엇을 안 건드리나

건드리는 자리는 **대장에 있는 쌍뿐이다.** 이것이 이중 안전장치다. 파서가 못 읽는
모양(이어붙이기, 배열)은 애초에 안 잡히고, 잡히더라도 대장에 없으면 안 건드린다.
잘못 읽어 조각난 문자열도 대장에 있을 리 없다.

중첩 삼항은 `unnest`가 평평한 갈림길 둘로 펴서 읽는다. 펴는 자리에도 안전장치가
따로 붙어 있어서, 하나라도 어긋나면 그 자리는 안 펴고 못 읽은 자리로 남는다.

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

#: 발췌의 길이. 미적용 목록이 영어를 자르는 폭과 같아서 보고의 두 목록이 나란히 읽힌다.
EXCERPT = 60

#: 못 읽은 까닭. **실제로 남은 자리에서 뽑은 것이라 둘뿐이다.** 없는 부류를 미리 만들지
#: 않는다 - 새 모양이 오면 `OTHER`로 나와서 보고가 그것을 지목한다.
CONCAT = "이어붙이기"
NOT_LITERAL = "리터럴이 아님"
OTHER = "기타"

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


@dataclass(frozen=True)
class Blind:
    """갈림길인 것은 알겠는데 이 파서가 못 읽은 자리.

    행 번호 하나로는 무엇이 왜 안 읽혔는지 알 수 없다. 업스트림이 파서 손 밖인 모양을
    더할 때 신호는 **숫자가 하나 오르는 것뿐이라**, 어느 멤버가 어떤 모양으로 늘었는지를
    보고가 스스로 말해야 한다.
    """

    #: 표식이 있는 줄.
    line: int
    #: 그 자리가 끝나는 줄. 여러 줄에 걸친 자리를 사람이 열어 보려면 범위가 필요하다.
    end_line: int
    #: 그 자리를 감싸는 멤버 이름. 모드가 로그에 적는 이름과 같다.
    name: str
    #: 왜 못 읽었나. `CONCAT`·`NOT_LITERAL`·`OTHER` 중 하나다.
    shape: str
    #: 그 자리의 앞부분을 한 줄로. 목록만 보고도 무엇인지 알아볼 만큼.
    excerpt: str


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
    #: 갈림길인 것은 알겠는데 못 읽은 자리.
    unreadable: list[Blind] = field(default_factory=list)


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


#: 조건에 있으면 안 펴는 부작용. 편 뒤에는 조건이 두 번 적히므로 두 번 일어난다.
SIDE_EFFECT = re.compile(r"\+\+|--|=>|\bawait\b|(?<![=!<>])=(?!=)")

#: 글 안의 (시작, 끝).
Span = tuple[int, int]


def _skip_literal(text: str, i: int) -> int:
    """`i`가 문자열 리터럴의 시작이면 그 끝을, 아니면 -1."""
    if text[i] == '"' or (text[i] == "$" and text[i + 1 : i + 2] == '"'):
        _, _, end = read_literal(text, i)
        return max(end, i + 1)
    return -1


def _top_question(text: str, start: int, end: int) -> int:
    """`text[start:end]`에서 최상위 갈림길의 `?`. 없으면 -1.

    괄호 안과 문자열 안은 안 본다. `??`와 `?.`는 갈림길이 아니라 건너뛴다.
    """
    depth = 0
    i = start
    while i < end:
        after = _skip_literal(text, i)
        if after >= 0:
            i = after
            continue
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0 and ch == "?":
            if text[i + 1 : i + 2] in ("?", "."):
                i += 2
                continue
            return i
        i += 1
    return -1


def _branch(text: str, start: int, end: int, stops: str, pending: int = 0) -> int:
    """갈래 하나를 읽고 멈춘 자리를 돌려준다. 안 멈추고 `end`까지 가면 -1.

    멈추는 자리는 최상위에서 만난 `stops`의 글자이거나, 짝 없이 나온 닫는 괄호다.
    괄호 깊이와 문자열 리터럴은 넘기고, 갈래 안에 또 갈림길이 있으면 그 `?`와 `:`를
    짝으로 세어 넘긴다. **괄호에 기대면 안 되기 때문이다** - C# 삼항은 우결합이라
    괄호 없이 중첩된 자리가 실제로 있고, 그 자리에서는 `?`와 `:`의 짝만이 갈래의 끝을
    말해 준다.

    `pending`은 이미 열려 있는 `?`의 수다. 갈림길 전체의 끝을 찾을 때 1로 시작한다.
    """
    depth = 0
    i = start
    while i < end:
        after = _skip_literal(text, i)
        if after >= 0:
            i = after
            continue
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif depth == 0 and ch == "?":
            if text[i + 1 : i + 2] in ("?", "."):
                i += 2
                continue
            pending += 1
        elif depth == 0 and ch == ":":
            if text[i + 1 : i + 2] == ":":
                i += 2  # `::`는 이름 공간 별칭이다
                continue
            if pending > 0:
                pending -= 1
            elif ch in stops:
                return i
        elif depth == 0 and ch in stops:
            return i
        i += 1
    return -1


def _peel(text: str, start: int, end: int) -> Span:
    """앞뒤 공백과, 조각 전체를 감싼 괄호를 벗긴다."""
    while True:
        while start < end and text[start] in " \t\r\n":
            start += 1
        while end > start and text[end - 1] in " \t\r\n":
            end -= 1
        if start >= end or text[start] != "(" or _branch(text, start + 1, end, "") != end - 1:
            return start, end
        start, end = start + 1, end - 1


def _split(text: str, start: int, end: int) -> tuple[Span, Span, Span] | None:
    """`cond ? A : B`를 (조건, 참 갈래, 거짓 갈래)로 가른다. 갈림길이 아니면 None."""
    start, end = _peel(text, start, end)
    question = _top_question(text, start, end)
    if question < 0:
        return None
    colon = _branch(text, question + 1, end, ":")
    if colon < 0 or text[colon] != ":":
        return None
    return (start, question), (question + 1, colon), (colon + 1, end)


def _piece(text: str, span: Span) -> str:
    return text[span[0] : span[1]].strip()


def _concatenated(text: str, start: int, end: int) -> bool:
    """갈래에 최상위 `+`가 있나. 조각이 여럿이면 리터럴 하나로 안 읽힌다."""
    depth = 0
    i = start
    while i < end:
        after = _skip_literal(text, i)
        if after >= 0:
            i = after
            continue
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0 and ch == "+":
            return True
        i += 1
    return False


def _shape(stripped: str, start: int, end: int) -> str:
    """왜 못 읽었나. 지금 남아 있는 자리에서 실제로 나오는 둘로 가른다."""
    colon = _branch(stripped, start, end, ":")
    if colon < 0 or stripped[colon] != ":":
        return OTHER  # 갈래를 못 가른다
    if _concatenated(stripped, start, colon) or _concatenated(stripped, colon + 1, end):
        return CONCAT
    return NOT_LITERAL


def _excerpt(text: str, start: int, end: int) -> str:
    """그 자리의 앞부분을 한 줄로. 줄바꿈이 섞이면 목록이 무너진다."""
    flat = " ".join(text[start:end].split())
    if len(flat) <= EXCERPT:
        return flat
    return flat[:EXCERPT].rstrip() + "…"


def _blind(stripped: str, text: str, span: int, question: int, line: int) -> Blind:
    """못 읽은 자리 하나를 사람이 볼 수 있는 모양으로 적는다.

    끝을 찾는 걸음은 `_flatten`이 갈림길 전체의 끝을 찾을 때와 같다. 못 읽는 자리라도
    `?`와 `:`의 짝은 셀 수 있어서, 어디까지가 그 자리인지는 알아낼 수 있다.
    """
    stop = _branch(stripped, question + 1, len(stripped), ":,;", pending=1)
    if stop < 0:
        # 끝을 못 찾으면 갈래도 못 가른다. 그 줄까지만 보이고 부류는 기타다.
        newline = text.find(_NEWLINE, span)
        return Blind(
            line=line,
            end_line=line,
            name=member_name(text, span),
            shape=OTHER,
            excerpt=_excerpt(text, span, len(text) if newline < 0 else newline),
        )
    return Blind(
        line=line,
        end_line=stripped.count(_NEWLINE, 0, stop) + 1,
        name=member_name(text, span),
        shape=_shape(stripped, question + 1, stop),
        excerpt=_excerpt(text, span, stop),
    )


def unnest(text: str) -> str:
    """중첩된 갈림길을 평평한 갈림길 둘로 편다.

        IsGerman ? (cond ? A_de : B_de) : (cond ? A_en : B_en)
        -> cond ? (IsGerman ? A_de : A_en) : (IsGerman ? B_de : B_en)

    안쪽 조건을 밖으로 끌어올리면 `IsGerman` 갈림길 둘이 다 리터럴 쌍이 되어, 그 뒤는
    `_ternary_sites`가 여느 자리와 똑같이 읽는다. 자리 하나에 쌍 여럿을 담는 길도
    있었지만 그러면 `Site`를 붙잡고 있는 곳이 전부 같이 바뀐다. 소스를 먼저 펴면
    바뀌는 곳이 이 함수 하나다.

    독일어와 영어는 **원문에서 잘라 온 글자 그대로** 다시 놓는다. 다시 조립하지도
    정규화하지도 않는다. 두 언어 사용자가 듣는 문장은 조립 전후로 같아야 한다.

    ## 안전장치 - 하나라도 어긋나면 그 자리를 그대로 둔다

    그러면 지금처럼 못 읽은 자리로 세어져 숫자에 남는다. 조용히 틀리게 펴는 것보다
    못 읽는 편이 낫다.

    1. 평평한 삼항은 안 건드린다. 양쪽이 리터럴이면 지금 경로 그대로다.
    2. 양쪽 갈래가 **둘 다** 삼항이어야 한다. 한쪽만 삼항인 자리는 안 편다.
    3. 안쪽 갈래가 또 삼항이면 안 편다. 갈래가 넷이 되어 짝이 안 맞는다.
    4. 안쪽 조건의 글자가 양쪽에서 같아야 한다. 독일어 쪽과 영어 쪽이 다른 조건으로
       갈리는데 뒤집으면 뜻이 달라진다.
    5. 조건에 부작용이 없어야 한다. 편 뒤에는 조건이 두 번 적힌다.

    여기에 둘을 더 뒀다. 식 안에 주석이 있으면 안 편다 - 조각을 옮기는 순간 `//` 뒤의
    글자가 딸려 가서 뒤따르는 코드를 주석이 삼킨다. 조각이 줄을 걸쳐도 안 편다 - 다시
    놓으면 들여쓰기가 무너지고, 그렇게 펴 봐야 안쪽이 리터럴이 아니라 어차피 못 읽는
    자리로 남는다.
    """
    stripped = strip_comments(text)
    edits: list[tuple[int, int, str]] = []
    at = 0
    while True:
        found = stripped.find(MARKER, at)
        if found < 0:
            break
        at = found + len(MARKER)

        question = _skip(stripped, at)
        if stripped[question : question + 1] != "?":
            continue
        if stripped[question + 1 : question + 2] in ("?", "."):
            continue

        edit = _flatten(stripped, text, found, question)
        if edit is not None:
            edits.append(edit)
            at = edit[1]  # 편 자리 안을 다시 훑지 않는다

    for begin, stop, replacement in reversed(edits):
        text = text[:begin] + replacement + text[stop:]
    return text


def _flatten(stripped: str, text: str, found: int, question: int) -> tuple[int, int, str] | None:
    """갈림길 하나를 편다. (시작, 끝, 그 자리에 놓을 글). 못 펴면 None."""
    stop = _branch(stripped, question + 1, len(stripped), ":,;", pending=1)
    if stop < 0:
        return None

    span, qualifier = _qualified(stripped, found)
    if text[span:stop] != stripped[span:stop]:
        return None  # 식 안에 주석이 있다

    colon = _branch(stripped, question + 1, stop, ":")
    if colon < 0 or stripped[colon] != ":":
        return None

    de = _split(stripped, question + 1, colon)
    en = _split(stripped, colon + 1, stop)
    if de is None or en is None:
        return None  # 안전장치 1·2 - 양쪽 갈래가 둘 다 삼항이어야 한다
    inner = (*de[1:], *en[1:])
    if any(_split(stripped, *piece) is not None for piece in inner):
        return None  # 안전장치 3 - 안쪽이 또 중첩이다

    condition = _piece(text, de[0])
    if condition != _piece(text, en[0]):
        return None  # 안전장치 4 - 양쪽이 다른 조건으로 갈린다
    if SIDE_EFFECT.search(condition):
        return None  # 안전장치 5 - 조건이 두 번 일어난다

    pieces = [condition, *(_piece(text, piece) for piece in inner)]
    if any(not piece or _NEWLINE in piece for piece in pieces):
        return None  # 줄을 걸친 조각은 다시 놓으면 들여쓰기가 무너진다

    condition, de_true, de_false, en_true, en_false = pieces
    marker = qualifier + MARKER
    first = f"{marker} ? {de_true} : {en_true}"
    second = f"{marker} ? {de_false} : {en_false}"

    line_start = text.rfind(_NEWLINE, 0, span) + 1
    single = f"{condition} ? ({first}) : ({second})"
    if span - line_start + len(single) <= WIDTH:
        return span, stop, single

    head = text[line_start:span]
    pad = " " * (len(head) - len(head.lstrip()) + 4)
    return span, stop, f"{condition}{_NEWLINE}{pad}? ({first}){_NEWLINE}{pad}: ({second})"


def scan(text: str) -> tuple[list[Site], list[Blind]]:
    """소스를 훑는다. (고칠 수 있는 자리, 갈림길인데 못 읽은 자리).

    못 읽은 곳도 같이 돌려주는 까닭은 **못 읽으면 못 세기** 때문이다. 중첩 삼항이나
    이어붙이기처럼 이 파서가 못 다루는 모양은 자리 목록에 아예 안 들어오므로,
    미적용 개수만 보면 그런 자리가 조용히 늘어도 신호가 없다. 그것을 따로 내면
    도구가 자기 사각지대의 크기를 스스로 말한다.
    """
    stripped = strip_comments(text)
    unreadable: list[Blind] = []
    sites = [*_ternary_sites(stripped, text, unreadable), *_pick_sites(stripped, text)]
    return sorted(sites, key=lambda site: site.start), sorted(
        unreadable, key=lambda blind: blind.line
    )


def find_sites(text: str) -> list[Site]:
    """소스에서 고칠 수 있는 자리를 위치와 함께 뽑는다."""
    return scan(text)[0]


def _ternary_sites(stripped: str, text: str, unreadable: list[Blind]) -> list[Site]:
    """아직 안 옮긴 `IsGerman ? de : en`.

    `?`까지 왔는데 양쪽을 리터럴로 못 읽으면 갈림길이긴 한데 이 파서의 손 밖이다.
    그 자리를 모양과 함께 `unreadable`에 남긴다.
    """
    sites: list[Site] = []
    start = 0
    while True:
        found = stripped.find(MARKER, start)
        if found < 0:
            return sites
        start = found + len(MARKER)

        question = _skip(stripped, start)
        if question >= len(stripped) or stripped[question] != "?":
            continue  # 갈림길이 아니다. 선언이거나 다른 쓰임이다

        line = stripped.count(_NEWLINE, 0, found) + 1
        span, qualifier = _qualified(stripped, found)

        i = _skip(stripped, question + 1)
        de, de_start, i = read_literal(stripped, i)
        if de is None:
            unreadable.append(_blind(stripped, text, span, question, line))
            continue
        de_end = i

        i = _skip(stripped, i)
        if i >= len(stripped) or stripped[i] != ":":
            unreadable.append(_blind(stripped, text, span, question, line))
            continue

        i = _skip(stripped, i + 1)
        en, en_start, i = read_literal(stripped, i)
        if en is None:
            unreadable.append(_blind(stripped, text, span, question, line))
            continue

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
    그 자리가 무엇인지만 `unreadable`로 나간다.

    ## 소스를 먼저 편다

    중첩 삼항은 `unnest`가 평평한 갈림길 둘로 펴 놓는다. 그래야 아래의 자리 찾기가
    여느 자리와 똑같이 읽는다. 펴는 것도 소스를 다시 쓰는 일이므로 여기 첫 줄에 둔다.
    """
    text = unnest(text)
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
