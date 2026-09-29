"""힐 모니터 한국어 음성을 만드는 계획과 음량 계산의 검사."""

from __future__ import annotations

import pytest

from hm_voice import WORDS, gain_db, plan, with_baseline


def test_the_plan_covers_every_file_the_bank_loads() -> None:
    # NumberVoiceBank가 읽는 이름: 1~8 × -35..35(5 간격), 그리고 dead·full.
    expected = {f"{n}_{p}.mp3" for n in range(1, 9) for p in range(-35, 40, 5)}
    expected |= {"dead.mp3", "full.mp3"}

    names = [item.name for item in plan()]

    assert len(names) == 122
    assert set(names) == expected


def test_pitch_factor_follows_the_bank_rule() -> None:
    by_name = {item.name: item for item in plan()}

    assert by_name["3_-35.mp3"].factor == pytest.approx(0.65)
    assert by_name["3_0.mp3"].factor == 1.0
    assert by_name["7_35.mp3"].factor == pytest.approx(1.35)
    assert by_name["7_35.mp3"].word == "7"


def test_dead_and_full_stay_at_natural_pitch() -> None:
    by_name = {item.name: item for item in plan()}

    assert by_name["dead.mp3"].factor == 1.0
    assert by_name["full.mp3"].factor == 1.0
    assert WORDS["dead"] == "전투불능"
    assert WORDS["full"] == "가득"


def test_gain_lifts_the_loudest_pitch_level_to_the_ceiling() -> None:
    # 한 낱말의 15단계에 같은 증폭을 쓴다. 가장 큰 단계(-3)가 천장(-1)에 닿는다.
    assert gain_db(peaks_db=[-12.0, -3.0, -8.0], ceiling_db=-1.0) == pytest.approx(2.0)


def test_gain_turns_down_a_word_already_over_the_ceiling() -> None:
    assert gain_db(peaks_db=[-4.0, -0.2], ceiling_db=-1.0) == pytest.approx(-0.8)


def test_baseline_keeps_other_entries_and_adds_the_audio() -> None:
    recorded = {"note": "n", "files": {"FF14Accessibility/Loc.cs": "aa"}}

    merged = with_baseline(recorded, {"FF14Accessibility/assets/partymonitor/1_0.mp3": "bb"})

    assert merged["note"] == "n"
    assert merged["files"] == {
        "FF14Accessibility/Loc.cs": "aa",
        "FF14Accessibility/assets/partymonitor/1_0.mp3": "bb",
    }
    # 입력은 건드리지 않는다.
    assert recorded["files"] == {"FF14Accessibility/Loc.cs": "aa"}
