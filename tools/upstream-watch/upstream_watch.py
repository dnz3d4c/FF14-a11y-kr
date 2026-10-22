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

## 같은 릴리스를 두 번 안 알리는 법

핀보다 새 것만 알리면 핀을 옮길 때까지 매일 같은 알림이 간다. 그래서 실행마다
**그날 받은 정식 릴리스의 태그 목록**을 남기고(`--write-seen`), 다음 실행은 직전
성공 실행이 남긴 목록에 **없는 태그만** 알린다(`--seen`). 워크플로가 그 목록을
아티팩트로 잇는다.

처음에는 직전 성공 실행의 시작 시각으로 갈랐다. 그러면 실행이 시작된 뒤 목록을 받기
전에 나온 릴리스를 다음 실행이 또 알린다. 끝난 시각으로 바꾸면 거꾸로 목록을 받은 뒤
끝나기 전에 나온 것을 놓친다. 목록은 시계를 안 보므로 둘 다 없다(사용자 결정: 정확히
알린다, 2026-10-22).

시각(`--since`)은 **목록이 없을 때만** 쓴다. 이 방식으로 바꾼 뒤 첫 실행과, 아티팩트가
만료될 만큼 실행이 오래 실패한 경우다.

**draft와 prerelease는 목록에 안 넣는다.** 넣으면 나중에 정식으로 올라온 날 이미 본
것으로 쳐서 알림이 빠진다.

사용법:
    uv run python tools/upstream-watch/upstream_watch.py --pin v6.08.129 \\
        --ours v6.8.129.0 --releases releases.json --seen prev/seen.json \\
        --since 2026-10-20T21:00:00Z --write-seen seen.json \\
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


def _published(rel: dict[str, Any]) -> bool:
    return not rel.get("draft") and not rel.get("prerelease")


def seen_tags(releases: list[dict[str, Any]]) -> list[str]:
    """다음 실행에 넘길 "이미 본" 목록. 정식 릴리스만 담는다."""
    return sorted(rel["tag_name"] for rel in releases if _published(rel))


def pick_new(
    releases: list[dict[str, Any]],
    pin: str,
    since: datetime | None,
    seen: set[str] | None = None,
) -> list[dict[str, Any]]:
    """핀보다 새 정식 릴리스 가운데 아직 안 알린 것. 최신이 앞이다.

    `seen`이 있으면 그것만으로 가르고 `since`는 안 본다. 빈 집합도 "목록이 있다"다.
    """
    base = parse_version(pin)
    if base is None:
        # 0으로 치면 원본 이력 전체가 새 버전이 되어 알림이 쏟아진다.
        raise ValueError(f"핀 태그를 못 읽었다: {pin!r}")

    picked = []
    for rel in releases:
        if not _published(rel):
            continue
        version = parse_version(rel.get("tag_name", ""))
        if version is None or version <= base:
            continue
        if seen is not None:
            if rel["tag_name"] in seen:
                continue
        elif since is not None and parse_time(rel["published_at"]) <= since:
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
    ap.add_argument("--seen", type=Path, help="직전 성공 실행이 남긴 목록. 파일이 없어도 된다")
    ap.add_argument("--since", default="", help="목록이 없을 때만 쓰는 직전 성공 실행 시각")
    ap.add_argument(
        "--ignore-since", action="store_true", help="시험용. 목록과 시각을 둘 다 안 본다"
    )
    ap.add_argument("--write-seen", type=Path, help="다음 실행에 넘길 목록을 여기 쓴다")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--out", required=True, type=Path, help="알릴 것이 있을 때만 쓴다")
    args = ap.parse_args(argv)

    releases = json.loads(args.releases.read_text(encoding="utf-8"))
    seen: set[str] | None = None
    if args.seen is not None and args.seen.is_file():
        seen = set(json.loads(args.seen.read_text(encoding="utf-8")))
    since = parse_time(args.since) if args.since else None

    if args.ignore_since:
        basis = "끔(시험)"
        new = pick_new(releases, args.pin, None)
    else:
        if seen is not None:
            basis = f"직전 실행이 본 정식 릴리스 {len(seen)}개"
        else:
            basis = f"목록 없음, 시각 {args.since}" if args.since else "없음(첫 실행)"
        new = pick_new(releases, args.pin, since, seen)

    if args.write_seen is not None:
        args.write_seen.write_text(json.dumps(seen_tags(releases)), encoding="utf-8")

    print("| | |")
    print("|---|---|")
    print(f"| 우리 핀 | {args.pin} |")
    print(f"| 우리 최신 릴리스 | {args.ours or '모름'} |")
    print(f"| 기준 | {basis} |")
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
