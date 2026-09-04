"""문서가 상한 안에 있는지, 그리고 손으로 적은 숫자가 실측과 맞는지 본다.

## 분량 상한

기존 저장소의 현황판은 14일 만에 138줄에서 1,748줄이 됐고, 그 사이 아무 장치도
소리를 내지 않았다. 여는 규칙만 있고 지우는 규칙이 없으면 문서는 반드시 자란다.
상한은 지우기를 강제하는 장치다 - 새 줄을 넣으려면 낡은 줄을 빼야 한다.

**이 검사는 막는다.** 분량은 우리가 정하는 값이라 실패가 곧 우리 잘못이다.

## 손으로 적은 숫자

현황판의 기준선 표는 조립 도구가 낸 값을 사람이 옮겨 적은 것이다. 옮겨 적은 숫자는
언젠가 실측과 갈라지고, 갈라진 것을 아무도 안 본다.

**이 검사는 막지 않는다.** 번역 잔량은 업스트림이 매일 흔드는 값이라, 문서가 하루
뒤처졌다고 머지를 막으면 빨간불이 신호이기를 그만둔다. 지목만 한다.

사용법:
    uv run python tools/docs-check/docs_check.py
    uv run python tools/docs-check/docs_check.py --report build/assemble-report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다

#: 상한을 건 문서. 여기 없는 문서는 재지 않는다.
LIMITS: dict[str, int] = {
    "docs/status.md": 120,
}

#: 기준선 표를 담은 문서.
BASELINE_DOC = "docs/status.md"

#: 표의 첫 칸에 적힌 이름 -> 조립 보고에서 그 값을 뽑는 열쇠들.
#: 값이 여럿인 줄은 표에 적힌 차례대로 늘어놓는다.
CITATIONS: dict[str, list[str]] = {
    "적용": ["applied_sites", "applied_rows"],
    "고아": ["orphans"],
    "미적용": ["untranslated"],
    "못 읽음": ["unreadable"],
    "튜플 사전": ["charamake"],
}

#: 표의 한 칸에서 수를 뽑는다. `3,023`처럼 천 단위 쉼표가 붙은 것도 한 수로 읽는다.
NUMBER = re.compile(r"\d[\d,]*")


@dataclass(frozen=True)
class Violation:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def over_limit(path: str, lines: list[str]) -> Violation | None:
    """상한을 넘었으면 위반을 돌려준다. 상한이 없는 문서는 재지 않는다."""
    limit = LIMITS.get(path)
    if limit is None or len(lines) <= limit:
        return None
    return Violation(path, f"{len(lines)}줄로 상한 {limit}줄을 넘었다")


def check_tree(root: Path) -> list[Violation]:
    """저장소의 상한 문서를 전부 잰다.

    **파일이 없는 것도 위반이다.** 상한을 건 문서가 사라졌는데 검사가 통과하면,
    그 문서를 지우는 것이 상한을 지키는 가장 쉬운 길이 된다.
    """
    violations: list[Violation] = []
    for path in sorted(LIMITS):
        target = root / path
        if not target.is_file():
            violations.append(Violation(path, "상한을 건 문서가 없다"))
            continue
        found = over_limit(path, target.read_text(encoding="utf-8").splitlines())
        if found is not None:
            violations.append(found)
    return violations


def _size(value: Any) -> int:
    """보고의 한 항목을 수로. 세어야 하는 것은 세고, 이미 수인 것은 그대로 둔다."""
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return len(value)
    # 튜플 사전은 파일마다 도우미별 건수를 갖는다. 합계끼리 더한다.
    return sum(int(counts["합계"]) for counts in value.values())


def report_numbers(report: dict[str, Any]) -> dict[str, list[int]]:
    """조립 보고에서, 문서가 인용하기로 한 숫자를 뽑는다."""
    return {name: [_size(report[key]) for key in keys] for name, keys in CITATIONS.items()}


def cited(text: str) -> dict[str, list[int]]:
    """문서의 표에서 인용된 숫자를 뽑는다. 첫 칸의 이름으로 줄을 찾는다."""
    found: dict[str, list[int]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] not in CITATIONS:
            continue
        found[cells[0]] = [int(n.replace(",", "")) for n in NUMBER.findall(cells[1])]
    return found


def drifted(text: str, report: dict[str, Any]) -> list[str]:
    """문서가 실측과 갈라진 자리. 비면 맞는 것이다."""
    wanted = report_numbers(report)
    written = cited(text)

    problems: list[str] = []
    for name, numbers in wanted.items():
        if name not in written:
            problems.append(f"{name}: 문서에 그 줄이 없다 - 실측은 {numbers}다")
        elif written[name] != numbers:
            problems.append(f"{name}: 문서는 {written[name]}인데 실측은 {numbers}다")
    return problems


def main(argv: list[str] | None = None) -> int:
    console.setup()
    parser = argparse.ArgumentParser(description="문서 검사.")
    parser.add_argument("--root", default=".", help="저장소 루트")
    parser.add_argument(
        "--report",
        type=Path,
        help=f"조립 보고. 주면 {BASELINE_DOC}의 기준선을 대조한다 - 어긋나도 막지 않는다",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.report is not None:
        problems = drifted(
            (root / BASELINE_DOC).read_text(encoding="utf-8"),
            json.loads(args.report.read_text(encoding="utf-8")),
        )
        for problem in problems:
            print(f"{BASELINE_DOC}: {problem}")
        if problems:
            print(f"\n{BASELINE_DOC}의 기준선을 실측에 맞춘다. 막지는 않는다.")
        else:
            print(f"{BASELINE_DOC}의 기준선이 실측과 맞는다.")
        return 0

    violations = check_tree(root)
    for violation in violations:
        print(violation, file=sys.stderr)

    if violations:
        print(
            "\n분량이 넘치면 줄이 아니라 무엇을 지울지를 정한다. "
            "끝난 것은 docs/changelog.md, 결함 하나하나는 docs/issues/가 갖는다.",
            file=sys.stderr,
        )
        return 1

    print(f"상한 문서 {len(LIMITS)}개가 전부 상한 안이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
