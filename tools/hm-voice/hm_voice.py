"""힐 모니터가 말하는 숫자와 상태 낱말을 한국어로 만들어 `replace/`에 둔다.

원본 음성 122개는 WoW 애드온 Sku의 영어 녹음이다. 한국어판은 윈도 음성 "Yuna"로 낱말을
합성하고 rubberband로 음높이를 옮긴다. 원본 작성자가 기각한 조합(옛 영어 SAPI 음성 +
위상 보코더)은 자음이 뭉개졌는데, rubberband의 과도음 처리(crisp)와 포먼트 보존과
짧은 분석 창을 쓰면 사용자 귀 판정에서 통과했다(2026-09-29).

**짧은 창이 필수다.** 낱말이 0.1초 남짓이라 기본 창은 0.65배를 0.83배까지만 내린다.

Yuna가 깔린 머신에서만 돈다. 산출물 mp3는 커밋되므로 조립과 CI는 이 도구를 안 부른다.

    uv run python tools/hm-voice/hm_voice.py
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
ASSET_DIR = "FF14Accessibility/assets/partymonitor"
BASELINE = REPO / "replace" / "upstream-baseline.json"

VOICE = "Yuna"
WORDS = {
    "1": "일",
    "2": "이",
    "3": "삼",
    "4": "사",
    "5": "오",
    "6": "육",
    "7": "칠",
    "8": "팔",
    "dead": "전투불능",
    "full": "가득",
}

#: NumberVoiceBank의 음높이 사다리: -35..35 퍼센트, 5 간격, 배율 = 1 + 퍼센트/100.
PITCH_PERCENTS = range(-35, 40, 5)

#: 원본 영어 숫자의 RMS가 -13.4~-13.9dB다. 한국어가 다른 소리보다 작게 들리지 않게 맞춘다.
TARGET_RMS_DB = -13.5
CEILING_DB = -1.0

#: 원본 NumberVoiceBank.Trim과 같은 문턱. 적재할 때 한 번 더 자르지만 파일도 맞춰 둔다.
TRIM = (
    "silenceremove=start_periods=1:start_threshold=0.004:detection=peak,areverse,"
    "silenceremove=start_periods=1:start_threshold=0.004:detection=peak,areverse"
)
#: 원본 규격: 22050Hz 스테레오.
FORMAT = "aresample=22050,aformat=sample_fmts=s16:channel_layouts=stereo"


@dataclass(frozen=True)
class Clip:
    name: str
    word: str
    factor: float


def plan() -> list[Clip]:
    """NumberVoiceBank가 읽는 파일 122개. dead·full은 원래 음높이다."""
    clips = [Clip(f"{n}_{p}.mp3", str(n), 1 + p / 100) for n in range(1, 9) for p in PITCH_PERCENTS]
    clips += [Clip("dead.mp3", "dead", 1.0), Clip("full.mp3", "full", 1.0)]
    return clips


def gain_db(rms_db: float, peak_db: float, target_rms_db: float, ceiling_db: float) -> float:
    """RMS를 목표로 올리거나 내리되 꼭짓점이 천장을 넘지 않게 한다."""
    return min(target_rms_db - rms_db, ceiling_db - peak_db)


def with_baseline(recorded: dict[str, Any], digests: dict[str, str]) -> dict[str, Any]:
    merged = copy.deepcopy(recorded)
    merged["files"].update(digests)
    return merged


def _run(args: list[str]) -> str:
    done = subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8")
    return done.stdout + done.stderr


def _synthesize(work: Path) -> None:
    lines = [
        "Add-Type -AssemblyName System.Speech",
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        f"$s.SelectVoice('{VOICE}')",
    ]
    for key, text in WORDS.items():
        lines.append(f"$s.SetOutputToWaveFile('{work / f'raw_{key}.wav'}'); $s.Speak('{text}')")
    lines.append("$s.Dispose()")
    script = work / "synth.ps1"
    # Windows PowerShell 5는 BOM 없는 UTF-8을 ANSI로 읽어 한글이 깨진다.
    script.write_text("\n".join(lines), encoding="utf-8-sig")
    _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)])


def _levels(path: Path) -> tuple[float, float]:
    """전체 채널의 (RMS dB, 꼭짓점 dB)."""
    out = _run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "astats", "-f", "null", "-"])
    overall = out.split("Overall", 1)[1]
    rms = re.search(r"RMS level dB: (-?[\d.]+)", overall)
    peak = re.search(r"Peak level dB: (-?[\d.]+)", overall)
    if rms is None or peak is None:
        raise RuntimeError(f"음량을 못 읽었다 - {path}")
    return float(rms.group(1)), float(peak.group(1))


def _pitch(factor: float) -> str:
    if factor == 1.0:
        return ""
    return f"rubberband=pitch={factor}:transients=crisp:formant=preserved:window=short,"


def _encode(src: Path, dst: Path, filters: str) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(src),
            "-af",
            filters,
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:a",
            "+bitexact",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(dst),
        ]
    )


def build(out_dir: Path, work: Path) -> None:
    _synthesize(work)

    gains: dict[str, float] = {}
    for key in WORDS:
        natural = work / f"natural_{key}.wav"
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(work / f"raw_{key}.wav"),
                "-af",
                f"{TRIM},{FORMAT}",
                str(natural),
            ]
        )
        gains[key] = gain_db(*_levels(natural), TARGET_RMS_DB, CEILING_DB)

    out_dir.mkdir(parents=True, exist_ok=True)
    for clip in plan():
        filters = f"{_pitch(clip.factor)}{TRIM},volume={gains[clip.word]:.2f}dB,{FORMAT}"
        _encode(work / f"raw_{clip.word}.wav", out_dir / clip.name, filters)


def record_baseline() -> None:
    """교체한 원본 파일의 지문을 기준선에 적는다. 원본이 음성을 바꾸면 조립이 알린다."""
    digests = {
        f"{ASSET_DIR}/{clip.name}": hashlib.sha256(
            (REPO / "upstream" / ASSET_DIR / clip.name).read_bytes()
        ).hexdigest()
        for clip in plan()
    }
    recorded = json.loads(BASELINE.read_text(encoding="utf-8"))
    merged = with_baseline(recorded, digests)
    BASELINE.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        build(REPO / "replace" / ASSET_DIR, Path(tmp))
    record_baseline()
    print(f"{len(plan())}개를 replace/{ASSET_DIR}에 만들었다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
