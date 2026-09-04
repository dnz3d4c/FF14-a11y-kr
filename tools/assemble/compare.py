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
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다

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
    new_unreadable: list[dict[str, Any]] = field(default_factory=list)
    gone_unreadable: list[dict[str, Any]] = field(default_factory=list)
    new_untranslated: list[dict[str, Any]] = field(default_factory=list)

    @property
    def moved(self) -> bool:
        return bool(
            self.new_orphans
            or self.gone_orphans
            or self.new_unreadable
            or self.gone_unreadable
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
        if self.new_unreadable:
            lines.append("### 새로 생긴 못 읽음")
            lines.append("")
            lines.append("업스트림이 파서 손 밖인 모양을 더했다는 신호다. 미적용에도 안 잡힌다.")
            lines.append("")
            lines += [_blind_line(site) for site in self.new_unreadable]
            lines.append("")
        if self.gone_unreadable:
            lines.append("### 사라진 못 읽음")
            lines.append("")
            lines += [_blind_line(site) for site in self.gone_unreadable]
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


def _blind_line(site: dict[str, Any]) -> str:
    """못 읽은 자리 하나를 본문의 한 줄로. 여러 줄에 걸치면 범위로 적는다."""
    line, end = site["line"], site["end_line"]
    where = f"{site['file']}:{line}" if end <= line else f"{site['file']}:{line}-{end}"
    return f"- `{where}` {site['name'] or '(이름 없음)'} [{site['shape']}] {site['excerpt']}"


def _blind(report: dict[str, Any]) -> list[dict[str, Any]] | None:
    """못 읽은 자리 목록. 자리를 못 가르는 옛 보고면 None.

    옛 보고는 `unreadable`이 `파일:행` 문자열 배열이라 멤버도 모양도 없다. 그런 보고와
    견주게 되면 증감 목록을 비우고 개수만 낸다 - 견주다 터지는 것보다 낫다.
    """
    sites = report["unreadable"]
    if any(not isinstance(site, dict) for site in sites):
        return None
    return list(sites)


def _blind_changes(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """못 읽은 자리의 (새로 생긴 것, 사라진 것).

    가르는 열쇠에 행 번호를 안 쓴다. 위쪽에 줄이 하나만 들어도 자리가 통째로 새것으로
    세어져, 정작 봐야 할 신호가 묻힌다. `(파일, 멤버, 모양)`이면 업스트림이 **어느 멤버에
    어떤 모양을 더했는지**가 그대로 나온다.
    """
    old, new = _blind(before), _blind(after)
    if old is None or new is None:
        return [], []

    def key(site: dict[str, Any]) -> tuple[str, str, str]:
        return (site["file"], site["name"], site["shape"])

    old_keys = {key(site) for site in old}
    new_keys = {key(site) for site in new}
    return (
        [site for site in new if key(site) not in old_keys],
        [site for site in old if key(site) not in new_keys],
    )


def _count(report: dict[str, Any], key: str) -> int:
    value = report[key]
    return value if isinstance(value, int) else len(value)


def compare(before: dict[str, Any], after: dict[str, Any]) -> Change:
    """옛 보고와 새 보고를 견준다."""
    old_orphans = _pairs(before)
    new_orphans = _pairs(after)
    old_sites = {(site["file"], site["name"], site["en"]) for site in before["untranslated"]}
    new_blind, gone_blind = _blind_changes(before, after)

    return Change(
        counts={name: (_count(before, key), _count(after, key)) for name, key in COUNTS.items()},
        new_orphans=[key for key in new_orphans if key not in set(old_orphans)],
        gone_orphans=[key for key in old_orphans if key not in set(new_orphans)],
        new_unreadable=new_blind,
        gone_unreadable=gone_blind,
        new_untranslated=[
            site
            for site in after["untranslated"]
            if (site["file"], site["name"], site["en"]) not in old_sites
        ],
    )


def main(argv: list[str] | None = None) -> int:
    console.setup()
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
