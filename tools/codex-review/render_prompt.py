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
UNTRACKED_EMPTY = "(none)"
KO_ONLY_EMPTY = "(이번 변경에 새로 더해진 한국어 문장이 없다)"
UPSTREAM_NOTES_EMPTY = "(원본 릴리스 노트를 못 받았다 — 대조 없이 판정한다)"
# diff에서 더해진 대장 줄의 `"ko": "..."` 값. 줄 머리에 있어야 한다 - 테스트나 문서가
# 예시로 든 "ko"까지 잡으면 리뷰어가 그것을 번역으로 읽는다. 뒤에 쉼표가 붙어도 잡는다.
KO_ADDED = re.compile(r'^\+\s*"ko"\s*:\s*"((?:[^"\\]|\\.)*)"')


def compose(template: str, fields: dict[str, str], diff: str) -> str:
    """diff에서 뽑는 자리까지 채워 프롬프트를 만든다."""
    return render(template, {**fields, "KO_ONLY": ko_only_block(diff)}, diff)


def untracked_block(paths: list[str]) -> str:
    """diff에 없는 새 파일 목록. 내용은 codex가 작업 트리에서 직접 읽는다."""
    return "\n".join(f"- {p}" for p in paths) if paths else UNTRACKED_EMPTY


def ko_only_block(diff: str) -> str:
    """diff에 더해진 한국어 문장만 번호를 붙여 낸다.

    원문을 본 사람은 빠진 정보를 머리로 채워 읽으므로, 한국어만 읽어서 뜻이
    서는지는 독일어와 영어를 가린 채로 판정해야 한다. 지워진 줄은 뺀다.
    """
    found: list[str] = []
    for line in diff.splitlines():
        match = KO_ADDED.search(line)
        if match and match.group(1) and match.group(1) not in found:
            found.append(match.group(1))
    if not found:
        return KO_ONLY_EMPTY
    return "\n".join(f"{i}. {v}" for i, v in enumerate(found, 1))


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
    untracked: list[str] | None = None,
    upstream_notes: str = UPSTREAM_NOTES_EMPTY,
) -> dict[str, str]:
    """저장소 맥락을 읽어 치환 값을 모은다."""
    return {
        "INTENT": intent,
        "CLAUDE_HYPOTHESIS": hypothesis,
        "PLAN_CONTEXT": plan,
        "REPO_CONTEXT": read_repo_context(root),
        "COMMIT_MESSAGES": commit_messages,
        "STASH_SHA": review_target,
        "UNTRACKED_FILES": untracked_block(untracked or []),
        "UPSTREAM_NOTES": upstream_notes,
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
    parser.add_argument(
        "--upstream-notes", default=None, help="원본 릴리스 노트 파일. 노트 리뷰의 대조 근거다"
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    template = (TEMPLATE_ROOT / args.template).read_text(encoding="utf-8")
    notes = (
        Path(args.upstream_notes).read_text(encoding="utf-8")
        if args.upstream_notes
        else UPSTREAM_NOTES_EMPTY
    )
    untracked = git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    fields = build_fields(
        root,
        intent=args.intent,
        hypothesis=args.hypothesis,
        plan=args.plan,
        untracked=untracked,
        upstream_notes=notes,
    )
    text = compose(template, fields, collect_diff(root, args.base))

    out = Path(tempfile.gettempdir()) / f"codex-review-prompt-{root.name}.txt"
    out.write_text(text, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
