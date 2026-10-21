"""원본 모드의 새 릴리스를 찾아 ntfy로 보낼 본문을 만든다.

`.github/workflows/sync.yml`이 매일 부른다. 이 도구는 **판정만 한다** - 원본
릴리스 목록과 직전 성공 실행 시각은 워크플로가 `gh`로 받아 넘기고, 보내는 것도
워크플로가 한다. 그래서 네트워크 없이 테스트로 잴 수 있다.

## 버전을 무엇과 견주는가

**서브모듈 핀의 태그와 견준다. 우리 버전 번호와 견주지 않는다.** 원본은
`v6.08.129`(세 마디, 앞자리 0)이고 우리는 `v6.8.129.0`(네 마디, 넷째는 한국어
개정)이다. 우리 번호에서 원본 태그를 역산하는 길은 끊겨 있다(`docs/decisions.md`
D-11). 핀은 우리가 실제로 얹은 원본이라 "얹을 것이 생겼다"의 기준으로 맞다.

견줄 때는 마디마다 정수로 읽는다. 문자열로 견주면 `v6.08.35`가 `v6.08.129`보다
커진다.

## 왜 직전 성공 실행 시각을 받는가

이슈를 안 쓰기로 해서(사용자 결정, 2026-10-21) "이미 알렸다"를 적어 둘 자리가
없다. 핀보다 새 것만 알리면 핀을 옮길 때까지 매일 같은 알림이 간다. 그래서
**직전 성공 실행이 시작한 뒤에 발행된 것**만 알린다. 실행 이력이 상태 몫을 한다.
하루를 건너뛰거나 실패해도 다음 성공 실행이 그 구간을 다시 훑는다.

사용법:
    uv run python tools/upstream-watch/upstream_watch.py --pin v6.08.129 \\
        --ours v6.8.129.0 --releases releases.json --since 2026-10-20T21:00:00Z \\
        --topic dewey-hermes --out payload.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다

_VERSION = re.compile(r"v(\d+(?:\.\d+)*)")

#: ntfy 우선순위. 경보 토픽의 5는 컨테이너 다운 같은 즉시 조치용이다. 원본 업데이트는
#: 조치가 필요하지만 급하지 않다.
PRIORITY = 3


def parse_version(tag: str) -> tuple[int, ...] | None:
    """`v6.08.129` → `(6, 8, 129)`. 못 읽으면 None."""
    m = _VERSION.fullmatch(tag.strip())
    if not m:
        return None
    return tuple(int(part) for part in m.group(1).split("."))


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def pick_new(
    releases: list[dict[str, Any]], pin: str, since: datetime | None
) -> list[dict[str, Any]]:
    """핀보다 새 버전이고 `since` 뒤에 발행된 정식 릴리스. 최신이 앞이다."""
    base = parse_version(pin)
    if base is None:
        # 0으로 치면 원본 이력 전체가 새 버전이 되어 알림이 쏟아진다.
        raise ValueError(f"핀 태그를 못 읽었다: {pin!r}")

    picked = []
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        version = parse_version(rel.get("tag_name", ""))
        if version is None or version <= base:
            continue
        if since is not None and parse_time(rel["published_at"]) <= since:
            continue
        picked.append((version, rel))
    picked.sort(key=lambda pair: pair[0], reverse=True)
    return [rel for _, rel in picked]


def pin_ahead_of_release(pin: str, ours: str) -> bool | None:
    """핀을 옮겼는데 우리 최신 릴리스가 아직 그 핀을 안 실었나. 모르면 None.

    우리 번호의 앞 세 마디는 원본 태그에서 앞자리 0만 뺀 값이라(D-11) 정수로 읽으면
    그대로 맞댈 수 있다. 역산이 아니라 같은 수를 읽는 것이다. "다르다"가 아니라
    방향을 본다 - 시험 핀은 우리 릴리스보다 뒤에 있다.
    """
    p, o = parse_version(pin), parse_version(ours)
    if p is None or o is None or len(o) != 4:
        return None
    return p[:3] > o[:3]


def build_payload(
    new: list[dict[str, Any]], pin: str, ours: str, *, topic: str, test: bool = False
) -> dict[str, Any]:
    latest = new[0]
    title = f"FF14 접근성 모드 원본 {latest['tag_name']} 발행"
    if test:
        title = f"[시험] {title}"
    lines = [
        f"원본 최신: {latest['tag_name']} ({latest['published_at'][:10]} 발행)",
        f"우리 핀: {pin}",
        f"우리 최신 릴리스: {ours or '모름'}",
    ]
    if len(new) > 1:
        lines.append(f"새 릴리스 {len(new)}개: " + ", ".join(r["tag_name"] for r in new))
    if pin_ahead_of_release(pin, ours):
        lines.append("핀은 이미 옮겼고 우리 릴리스는 아직 발행 전이다.")
    # `tags`는 넣지 않는다. 폰 클라이언트가 이모지로 그린다.
    return {
        "topic": topic,
        "title": title,
        "message": "\n".join(lines),
        "priority": PRIORITY,
        "click": latest["html_url"],
    }


def main(argv: list[str] | None = None) -> int:
    console.setup()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pin", required=True, help="서브모듈 핀의 원본 태그")
    ap.add_argument("--ours", default="", help="우리 최신 릴리스 태그. 표시에만 쓴다")
    ap.add_argument("--releases", required=True, type=Path, help="원본 릴리스 목록 JSON")
    ap.add_argument("--since", default="", help="직전 성공 실행 시작 시각. 없으면 첫 실행")
    ap.add_argument("--ignore-since", action="store_true", help="시험용. 시각 조건을 끈다")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--out", required=True, type=Path, help="알릴 것이 있을 때만 쓴다")
    args = ap.parse_args(argv)

    releases = json.loads(args.releases.read_text(encoding="utf-8"))
    since = None if args.ignore_since or not args.since else parse_time(args.since)
    new = pick_new(releases, args.pin, since)

    print("| | |")
    print("|---|---|")
    print(f"| 우리 핀 | {args.pin} |")
    print(f"| 우리 최신 릴리스 | {args.ours or '모름'} |")
    print(f"| 기준 시각 | {'끔(시험)' if args.ignore_since else args.since or '없음(첫 실행)'} |")
    print()
    if not new:
        print("알릴 새 원본 릴리스가 없다.")
        return 0

    payload = build_payload(new, args.pin, args.ours, topic=args.topic, test=args.ignore_since)
    args.out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"알린다: {payload['title']}")
    print()
    print(payload["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
