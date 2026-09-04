"""원본 파일 안의 특정 자리에 우리 것을 덧댄다.

## 왜 규칙이 데이터인가

원본 파일을 통째로 대체하면 그 파일에 대한 원본의 개선을 조용히 덮어쓴다. 반대로
손으로 쓴 diff로 얹으면 원본이 그 근처를 고칠 때마다 충돌을 손으로 푼다. 규칙을
데이터로 두면 실패 모양이 바뀐다. **앵커를 못 찾았다**가 되고, 그때 어느 규칙인지
이름이 나온다.

## 아무 데나 넣지 않는다

앵커가 하나도 안 잡히거나 여러 곳에서 잡히면 넣지 않고 규칙 이름을 대며 실패한다.
잘못 끼우면 컴파일이 깨지고, 그건 규칙을 쓴 사람이 알아야 할 일이다. 여러 곳에서
잡히는 경우가 특히 위험하다. 첫 자리에 넣는 것은 그럴듯하게 성공하지만 어느 자리가
맞는지는 아무도 결정한 적이 없다.

## 고정 문자열과 정규식

규칙마다 `find`(고정 문자열)나 `regex`(정규식) 중 하나를 쓴다. 정규식이 필요한
자리는 원본 판마다 값이 바뀌는 곳이다. `<Version>`이 그렇고, 고정 문자열로 적으면
다음 판에서 앵커가 통째로 깨진다.

## 한국어 주입 앞뒤

규칙은 한국어 주입 **뒤**에 도는 것이 기본이다. 주입이 대장으로 열지 못하는 자리,
곧 원본에 아예 없는 멤버나 원본 판마다 값이 바뀌는 자리를 다루기 때문이다.

`"phase": "before"`를 적으면 주입 **앞**에 돈다. 규칙이 고치는 것이 대장의 키인
독일어나 영어 문장 자체일 때 그렇게 한다. 뒤에 돌면 주입이 이미 지나간 뒤라 그
문장이 대장과 못 만나고, 한국어가 영영 안 들어간다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import files

#: 규칙이 도는 때. 한국어 주입 앞과 뒤.
BEFORE = "before"
AFTER = "after"


@dataclass(frozen=True)
class Rule:
    """원본 파일 한 곳을 바꾸는 규칙 하나."""

    name: str
    file: str
    replace: str
    #: 고정 문자열 앵커. `pattern`과 둘 중 하나만 갖는다.
    find: str | None = None
    #: 정규식 앵커. `replace`에서 역참조를 쓸 수 있다.
    pattern: str | None = None
    #: 한국어 주입 앞뒤 중 어디서 도는가. `before` 또는 `after`.
    phase: str = AFTER
    #: 왜 이 규칙이 있는지. 도구는 안 읽고 사람이 읽는다.
    why: str = ""


def _text(value: str | list[str] | None) -> str | None:
    """규칙의 문자열 값. 배열이면 줄 목록으로 읽는다.

    앵커는 대개 온전한 줄이라, JSON 안에서 `\\n`을 이어 붙인 한 줄짜리 문자열로
    적으면 사람이 못 읽는다. 배열로 적으면 줄이 줄로 보인다. 줄 목록은 `\\n`으로
    잇고 끝에도 `\\n`을 붙인다 - 줄 단위 앵커가 다음 줄을 삼키지 않게 하기 위해서다.
    줄 가운데를 잡아야 하는 규칙은 문자열로 적는다.
    """
    if value is None or isinstance(value, str):
        return value
    return "".join(line + "\n" for line in value)


def load_rules(path: Path) -> list[Rule]:
    """규칙 파일을 읽는다. 모양이 깨져 있으면 ValueError."""
    document = json.loads(path.read_text(encoding="utf-8"))
    rules: list[Rule] = []
    names: set[str] = set()

    for row in document["rules"]:
        name = row["name"]
        if name in names:
            raise ValueError(f"규칙 이름이 겹친다: {name}")
        names.add(name)

        find = _text(row.get("find"))
        pattern = _text(row.get("regex"))
        if (find is None) == (pattern is None):
            raise ValueError(f"{name}: `find`와 `regex` 둘 중 하나만 적는다")

        phase = row.get("phase", AFTER)
        if phase not in (BEFORE, AFTER):
            raise ValueError(f"{name}: `phase`는 `{BEFORE}`나 `{AFTER}`다 - {phase}")

        replace = _text(row["replace"])
        assert replace is not None
        rules.append(
            Rule(
                name=name,
                file=row["file"],
                replace=replace,
                find=find,
                pattern=pattern,
                phase=phase,
                why=row.get("why", ""),
            )
        )
    return rules


def _matches(rule: Rule, text: str) -> list[tuple[int, int, str]]:
    """(시작, 끝, 넣을 것). 정규식이면 역참조를 펼친 결과가 들어간다."""
    if rule.find is not None:
        return [
            (found, found + len(rule.find), rule.replace) for found in _find_all(text, rule.find)
        ]
    assert rule.pattern is not None
    return [
        (match.start(), match.end(), match.expand(rule.replace))
        for match in re.finditer(rule.pattern, text)
    ]


def _find_all(text: str, needle: str) -> list[int]:
    found: list[int] = []
    start = 0
    while True:
        at = text.find(needle, start)
        if at < 0:
            return found
        found.append(at)
        start = at + len(needle)


def apply_rules(rules: list[Rule], root: Path, phase: str = AFTER) -> list[str]:
    """그 때에 도는 규칙을 트리에 적용한다. 문제 목록을 돌려준다 - 비면 통과.

    한 규칙이 실패해도 나머지를 다 본다. 첫 실패에서 멈추면 두 번째 문제를 다음
    판에서야 만나고, 그때는 원인이 둘로 늘어 있다.
    """
    problems: list[str] = []

    for rule in rules:
        if rule.phase != phase:
            continue
        target = root / rule.file
        if not target.is_file():
            problems.append(f"{rule.name}: 대상 파일이 없다 - {rule.file}")
            continue

        text = files.read(target)
        found = _matches(rule, text)
        if not found:
            problems.append(f"{rule.name}: 앵커를 못 찾았다 - {rule.file}")
            continue
        if len(found) > 1:
            problems.append(
                f"{rule.name}: 앵커가 {len(found)}곳에서 잡혔다 - {rule.file}. "
                "어디에 넣을지 모르므로 넣지 않는다"
            )
            continue

        start, end, replacement = found[0]
        files.write(target, text[:start] + replacement + text[end:])

    return problems
