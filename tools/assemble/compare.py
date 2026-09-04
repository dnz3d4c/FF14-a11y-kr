"""조립 보고 둘을 견준다. 새 판을 얹을 때 무엇이 달라졌는지가 이 도구의 답이다.

## 왜 두 벌을 견주나

새 판의 절대 숫자만으로는 사람이 판단을 못 한다. "고아 7행"이 늘어난 것인지 원래
그랬던 것인지가 안 보이기 때문이다. 문서에 적어 둔 기준선과 대는 방법도 있지만, 그
숫자는 손으로 옮겨 적은 것이라 언젠가 실제와 갈라진다.

그래서 **옛 핀으로 한 번, 새 태그로 한 번 조립해서 그 둘을 견준다.** 기준선이 손이
아니라 실측이 되고, 동기화가 내는 PR 본문이 "무엇이 달라졌는가"를 그대로 담는다.

## 고아를 맨 앞에 둔다

고아는 대장에는 있는데 소스에서 못 만난 쌍이고, **업스트림이 그 문장을 고쳤다는
신호다.** 새 판을 받을 때 사람이 가장 먼저 봐야 하는 것이라 본문 맨 앞에 온다.

사용법:
    uv run python tools/assemble/compare.py before.json after.json --out body.md
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: 보고에서 숫자를 뽑는 법. 이름은 사람이 읽을 이름이다.
COUNTS: dict[str, str] = {
    "적용": "applied_sites",
    "대장 행": "applied_rows",
    "고아": "orphans",
    "미적용": "untranslated",
    "못 읽음": "unreadable",
}


@dataclass
class Change:
    """옛 보고에서 새 보고로 오면서 달라진 것."""

    #: 이름 -> (전, 후).
    counts: dict[str, tuple[int, int]] = field(default_factory=dict)
    new_orphans: list[tuple[str, str]] = field(default_factory=list)
    gone_orphans: list[tuple[str, str]] = field(default_factory=list)
    new_untranslated: list[dict[str, Any]] = field(default_factory=list)

    @property
    def moved(self) -> bool:
        return bool(
            self.new_orphans
            or self.gone_orphans
            or self.new_untranslated
            or any(before != after for before, after in self.counts.values())
        )

    def as_markdown(self) -> str:
        """PR 본문과 잡 요약에 그대로 들어갈 글."""
        if not self.moved:
            return "조립 결과에 달라진 것이 없다.\n"

        lines: list[str] = []
        if self.new_orphans:
            lines.append("### 새로 생긴 고아")
            lines.append("")
            lines.append("업스트림이 이 문장을 고쳤다는 신호다. 대장을 맞춰야 한다.")
            lines.append("")
            for de, en in self.new_orphans:
                lines.append(f"- `{en}` (독일어 `{de}`)")
            lines.append("")
        if self.gone_orphans:
            lines.append("### 사라진 고아")
            lines.append("")
            for de, en in self.gone_orphans:
                lines.append(f"- `{en}` (독일어 `{de}`)")
            lines.append("")

        lines.append("### 숫자")
        lines.append("")
        lines.append("| 이름 | 전 | 후 |")
        lines.append("|------|-----|-----|")
        for name, (before, after) in self.counts.items():
            mark = "" if before == after else f" ({after - before:+d})"
            lines.append(f"| {name} | {before} | {after}{mark} |")
        lines.append("")

        lines.append("### 새로 생긴 미적용")
        lines.append("")
        if self.new_untranslated:
            lines.append("영어로 나가고 모드가 로그에 남긴다.")
            lines.append("")
            for site in self.new_untranslated:
                where = f"{site['file']}:{site['line']}"
                lines.append(f"- `{where}` {site['name'] or '(이름 없음)'} - {site['en']}")
        else:
            lines.append("없다.")
        lines.append("")
        return "\n".join(lines)


def _pairs(report: dict[str, Any]) -> list[tuple[str, str]]:
    return [(row["de"], row["en"]) for row in report["orphans"]]


def _count(report: dict[str, Any], key: str) -> int:
    value = report[key]
    return value if isinstance(value, int) else len(value)


def compare(before: dict[str, Any], after: dict[str, Any]) -> Change:
    """옛 보고와 새 보고를 견준다."""
    old_orphans = _pairs(before)
    new_orphans = _pairs(after)
    old_sites = {(site["file"], site["name"], site["en"]) for site in before["untranslated"]}

    return Change(
        counts={name: (_count(before, key), _count(after, key)) for name, key in COUNTS.items()},
        new_orphans=[key for key in new_orphans if key not in set(old_orphans)],
        gone_orphans=[key for key in old_orphans if key not in set(new_orphans)],
        new_untranslated=[
            site
            for site in after["untranslated"]
            if (site["file"], site["name"], site["en"]) not in old_sites
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="조립 보고 둘을 견준다.")
    parser.add_argument("before", type=Path, help="옛 핀으로 조립한 보고")
    parser.add_argument("after", type=Path, help="새 태그로 조립한 보고")
    parser.add_argument("--out", type=Path, help="글을 적을 파일. 없으면 화면에만 낸다")
    args = parser.parse_args(argv)

    change = compare(
        json.loads(args.before.read_text(encoding="utf-8")),
        json.loads(args.after.read_text(encoding="utf-8")),
    )
    body = change.as_markdown()
    print(body)
    if args.out is not None:
        args.out.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
