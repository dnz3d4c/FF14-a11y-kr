"""분량 상한을 건 문서가 그 안에 있는지 본다.

기존 저장소의 현황판은 14일 만에 138줄에서 1,748줄이 됐고, 그 사이 아무 장치도
소리를 내지 않았다. 여는 규칙만 있고 지우는 규칙이 없으면 문서는 반드시 자란다.
상한은 지우기를 강제하는 장치다 - 새 줄을 넣으려면 낡은 줄을 빼야 한다.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

#: 상한을 건 문서. 여기 없는 문서는 재지 않는다.
LIMITS: dict[str, int] = {
    "docs/status.md": 120,
}


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="저장소 루트")
    args = parser.parse_args(argv)

    violations = check_tree(Path(args.root).resolve())
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
