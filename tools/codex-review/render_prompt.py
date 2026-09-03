"""codex 교차 리뷰에 넘길 프롬프트를 렌더한다.

이 저장소의 산출물은 전부 codex 교차 리뷰를 거친다. 그때마다 같은 자리표시자를
손으로 채우면 순서를 틀리기 쉬워서 도구로 고정한다. 결과 프롬프트는 저장소가 아니라
운영체제의 임시 디렉토리에 낸다.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATE_ROOT = Path.home() / ".claude" / "codex-prompts"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
MAX_DIFF_LINES = 5000
PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
NO_CONTEXT = "(저장소 맥락 없음)"


def render(template: str, fields: dict[str, str], diff: str) -> str:
    """자리표시자를 채운다.

    diff는 반드시 맨 마지막에 넣는다. 먼저 넣으면 뒤따르는 치환이 diff 본문 안의
    자리표시자까지 훑어서 리뷰어가 실제 코드가 아닌 것을 검토하게 된다.
    """
    text = template
    for key, value in fields.items():
        text = text.replace("{{" + key + "}}", value)

    unfilled = {name for name in PLACEHOLDER.findall(text) if name != "DIFF_OR_STAT"}
    if unfilled:
        raise ValueError(f"채우지 않은 자리표시자가 남았다: {', '.join(sorted(unfilled))}")

    return text.replace("{{DIFF_OR_STAT}}", diff)


def build_fields(
    root: Path,
    *,
    intent: str,
    hypothesis: str,
    plan: str,
    commit_messages: str = "(이번 범위에 커밋이 없다 — 미커밋 변경만 있다)",
    review_target: str = "(커밋 이전의 스테이징된 트리다)",
) -> dict[str, str]:
    """저장소 맥락을 읽어 치환 값을 모은다."""
    return {
        "INTENT": intent,
        "CLAUDE_HYPOTHESIS": hypothesis,
        "PLAN_CONTEXT": plan,
        "REPO_CONTEXT": read_repo_context(root),
        "COMMIT_MESSAGES": commit_messages,
        "STASH_SHA": review_target,
    }


def read_repo_context(root: Path) -> str:
    """`.claude/codex-review.json`의 맥락을 목록으로 만든다.

    이 맥락이 없으면 codex가 서브모듈 구조를 몰라서 '파일이 없다'는 오탐을 낸다.
    """
    path = root / ".claude" / "codex-review.json"
    if not path.exists():
        return NO_CONTEXT

    entries = json.loads(path.read_text(encoding="utf-8")).get("context", [])
    if not entries:
        return NO_CONTEXT
    return "\n".join(f"- {line}" for line in entries)


def collect_diff(root: Path, base: str | None) -> str:
    """스테이징된 변경을 base와 대조한다. 너무 길면 파일 목록만 낸다."""
    target = base or (EMPTY_TREE if not has_commits(root) else "HEAD")
    diff = git(root, "diff", "--cached", target)
    if len(diff.splitlines()) > MAX_DIFF_LINES:
        return git(root, "diff", "--cached", "--stat", target)
    return diff


def has_commits(root: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return result.returncode == 0


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패: {result.stderr.strip()}")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intent", required=True, help="이번 변경의 목적")
    parser.add_argument("--hypothesis", required=True, help="이 설계를 고른 근거")
    parser.add_argument("--plan", required=True, help="승인된 플랜의 현재 단계")
    parser.add_argument("--base", default=None, help="대조 기준. 생략하면 HEAD 또는 빈 트리")
    parser.add_argument(
        "--template", default="review.md", help="~/.claude/codex-prompts 아래의 템플릿 이름"
    )
    parser.add_argument("--root", default=".", help="저장소 루트")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    template = (TEMPLATE_ROOT / args.template).read_text(encoding="utf-8")
    fields = build_fields(root, intent=args.intent, hypothesis=args.hypothesis, plan=args.plan)
    text = render(template, fields, collect_diff(root, args.base))

    out = Path(tempfile.gettempdir()) / f"codex-review-prompt-{root.name}.txt"
    out.write_text(text, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
