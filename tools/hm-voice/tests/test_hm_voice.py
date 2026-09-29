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


def test_gain_lifts_a_quiet_word_to_the_target_loudness() -> None:
    assert gain_db(rms_db=-24.0, peak_db=-12.0, target_rms_db=-13.5, ceiling_db=-1.0) == (
        pytest.approx(10.5)
    )


def test_gain_stops_before_the_peak_clips() -> None:
    # RMS로는 12dB를 올려야 하지만 꼭짓점이 -5라 4dB에서 멈춘다.
    assert gain_db(rms_db=-25.5, peak_db=-5.0, target_rms_db=-13.5, ceiling_db=-1.0) == (
        pytest.approx(4.0)
    )


def test_gain_may_turn_a_loud_word_down() -> None:
    assert gain_db(rms_db=-10.0, peak_db=-2.0, target_rms_db=-13.5, ceiling_db=-1.0) == (
        pytest.approx(-3.5)
    )


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
