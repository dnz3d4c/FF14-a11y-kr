"""원본 업데이트 알림의 판정 테스트.

지키려는 것 셋.

- **버전은 마디별 숫자로 견준다.** 원본은 `v6.08.129`, 우리는 `v6.8.129.0`이다.
  문자열로 견주면 `v6.08.35`가 `v6.08.129`보다 커진다
- **한 릴리스는 한 번만 알린다.** 상태를 둘 자리가 없어서 직전 성공 실행 시각이
  그 몫을 한다. 핀을 옮길 때까지 매일 같은 알림이 가면 알림이 신호이기를 그만둔다
- **우리 번호에서 원본 태그를 역산하지 않는다.** 비교 기준은 서브모듈 핀이다
"""

import json
from datetime import datetime

import pytest

import upstream_watch as uw


def release(tag: str, published: str, *, draft: bool = False, pre: bool = False) -> dict:
    return {
        "tag_name": tag,
        "published_at": published,
        "draft": draft,
        "prerelease": pre,
        "html_url": f"https://github.com/o/r/releases/tag/{tag}",
    }


def at(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@pytest.mark.parametrize(
    ("older", "newer"),
    [
        ("v6.08.9", "v6.08.10"),
        ("v6.08.35", "v6.08.129"),
        ("v5.96", "v6.08.20"),
    ],
)
def test_versions_compare_by_number_not_text(older: str, newer: str) -> None:
    a, b = uw.parse_version(older), uw.parse_version(newer)
    assert a is not None and b is not None
    assert a < b


def test_leading_zero_is_the_same_number() -> None:
    """D-11: 우리 번호는 원본의 앞자리 0만 뺀 값이다."""
    assert uw.parse_version("v6.08.129") == uw.parse_version("v6.8.129")


@pytest.mark.parametrize("tag", ["", "latest", "dalamud-kr-full-15.0.3.7", "v6.08.x"])
def test_unreadable_tag_is_none(tag: str) -> None:
    assert uw.parse_version(tag) is None


def test_only_releases_newer_than_pin() -> None:
    releases = [
        release("v6.08.130", "2026-10-21T10:00:00Z"),
        release("v6.08.129", "2026-10-17T19:20:01Z"),
        release("v6.08.35", "2026-09-28T09:39:06Z"),
    ]
    picked = uw.pick_new(releases, "v6.08.129", since=at("2026-10-20T21:00:00Z"))
    assert [r["tag_name"] for r in picked] == ["v6.08.130"]


def test_release_already_seen_by_last_run_is_not_sent_again() -> None:
    releases = [release("v6.08.130", "2026-10-21T10:00:00Z")]
    assert uw.pick_new(releases, "v6.08.129", since=at("2026-10-21T21:00:00Z")) == []


def test_several_new_releases_come_newest_first() -> None:
    releases = [
        release("v6.08.130", "2026-10-21T10:00:00Z"),
        release("v6.08.131", "2026-10-21T15:00:00Z"),
    ]
    picked = uw.pick_new(releases, "v6.08.129", since=at("2026-10-20T21:00:00Z"))
    assert [r["tag_name"] for r in picked] == ["v6.08.131", "v6.08.130"]


def test_draft_and_prerelease_are_not_updates() -> None:
    releases = [
        release("v6.08.131", "2026-10-21T15:00:00Z", draft=True),
        release("v6.08.130", "2026-10-21T10:00:00Z", pre=True),
    ]
    assert uw.pick_new(releases, "v6.08.129", since=at("2026-10-20T21:00:00Z")) == []


def test_first_run_without_history_sends_what_is_newer() -> None:
    releases = [release("v6.08.130", "2025-01-01T00:00:00Z")]
    picked = uw.pick_new(releases, "v6.08.129", since=None)
    assert [r["tag_name"] for r in picked] == ["v6.08.130"]


def test_unreadable_pin_stops_instead_of_sending_everything() -> None:
    """핀을 못 읽었는데 0으로 치면 원본 이력 전체가 새 버전이 된다."""
    with pytest.raises(ValueError):
        uw.pick_new([release("v6.08.130", "2026-10-21T10:00:00Z")], "", since=None)


@pytest.mark.parametrize(
    ("pin", "ours", "expected"),
    [
        ("v6.08.129", "v6.8.129.0", False),
        ("v6.08.130", "v6.8.129.0", True),
        # 시험 핀이 우리 릴리스보다 뒤일 때. "다르다"만 보면 여기서 틀린다.
        ("v6.08.35", "v6.8.129.0", False),
        ("v6.08.129", "", None),
        ("v6.08.129", "dalamud-kr-full-15.0.3.7", None),
    ],
)
def test_pin_ahead_of_our_release(pin: str, ours: str, expected: bool | None) -> None:
    assert uw.pin_ahead_of_release(pin, ours) is expected


def test_payload_names_all_three_versions() -> None:
    new = [release("v6.08.130", "2026-10-21T10:00:00Z")]
    payload = uw.build_payload(new, "v6.08.129", "v6.8.129.0", topic="t")
    assert payload["topic"] == "t"
    assert "v6.08.130" in payload["title"]
    for tag in ("v6.08.130", "v6.08.129", "v6.8.129.0"):
        assert tag in payload["message"]
    assert payload["click"] == new[0]["html_url"]
    assert "tags" not in payload  # 폰 클라이언트가 이모지로 그린다


def test_payload_says_when_pin_is_ahead_of_release() -> None:
    new = [release("v6.08.131", "2026-10-21T10:00:00Z")]
    payload = uw.build_payload(new, "v6.08.130", "v6.8.129.0", topic="t")
    assert "발행 전" in payload["message"]


def test_payload_is_quiet_when_pin_is_behind_release() -> None:
    new = [release("v6.08.129", "2026-10-17T19:20:01Z")]
    payload = uw.build_payload(new, "v6.08.35", "v6.8.129.0", topic="t", test=True)
    assert "발행 전" not in payload["message"]


def test_main_writes_payload_only_when_there_is_news(tmp_path) -> None:
    releases = tmp_path / "releases.json"
    releases.write_text(json.dumps([release("v6.08.130", "2026-10-21T10:00:00Z")]), "utf-8")
    out = tmp_path / "payload.json"
    args = [
        "--pin",
        "v6.08.129",
        "--ours",
        "v6.8.129.0",
        "--releases",
        str(releases),
        "--topic",
        "t",
        "--out",
        str(out),
    ]

    assert uw.main([*args, "--since", "2026-10-21T21:00:00Z"]) == 0
    assert not out.exists()

    assert uw.main([*args, "--since", "2026-10-20T21:00:00Z"]) == 0
    assert json.loads(out.read_text("utf-8"))["title"].count("v6.08.130") == 1


def test_main_test_pin_ignores_time(tmp_path) -> None:
    """평소에 안 타는 알림 경로를 러너에서 실증하려고 둔 갈래다."""
    releases = tmp_path / "releases.json"
    releases.write_text(json.dumps([release("v6.08.129", "2026-10-17T19:20:01Z")]), "utf-8")
    out = tmp_path / "payload.json"
    code = uw.main(
        [
            "--pin",
            "v6.08.128",
            "--ours",
            "v6.8.129.0",
            "--releases",
            str(releases),
            "--topic",
            "t",
            "--out",
            str(out),
            "--since",
            "2026-10-21T21:00:00Z",
            "--ignore-since",
        ]
    )
    assert code == 0
    assert "시험" in json.loads(out.read_text("utf-8"))["title"]


def test_time_keeps_timezone() -> None:
    assert uw.parse_time("2026-10-21T10:00:00Z").utcoffset() is not None
