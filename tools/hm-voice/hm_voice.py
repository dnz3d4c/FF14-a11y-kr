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

#: 꼭짓점이 넘치지 않는 선에서 최대로 키운다(2026-09-29 사용자 요청). mp3 인코딩이
#: 꼭짓점을 조금 넘길 수 있어서 0이 아니라 -1dBFS에서 멈춘다.
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


def gain_db(peaks_db: list[float], ceiling_db: float) -> float:
    """한 낱말의 모든 음높이 단계 중 가장 큰 꼭짓점이 천장에 닿게 하는 증폭.

    단계마다 따로 키우면 같은 낱말이 음높이에 따라 크기가 달라진다. 그래서 한 값을 쓴다.
    """
    return ceiling_db - max(peaks_db)


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


def peak_db(path: Path) -> float:
    """전체 채널의 꼭짓점 dB."""
    out = _run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "astats", "-f", "null", "-"])
    found = re.search(r"Peak level dB: (-?[\d.]+)", out.split("Overall", 1)[1])
    if found is None:
        raise RuntimeError(f"꼭짓점을 못 읽었다 - {path}")
    return float(found.group(1))


def _pitch(factor: float) -> str:
    if factor == 1.0:
        return ""
    return f"rubberband=pitch={factor}:transients=crisp:formant=preserved:window=short,"


def _ffmpeg(src: Path, dst: Path, filters: str, *codec: str) -> None:
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", filters, *codec, str(dst)])


MP3 = (
    "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact",
    "-c:a", "libmp3lame", "-q:a", "2",
)  # fmt: skip


def build(out_dir: Path, work: Path) -> None:
    _synthesize(work)

    # 증폭 전의 단계별 소리를 먼저 만들어 꼭짓점을 잰다. 음높이를 옮기면 꼭짓점이 바뀐다.
    staged: dict[str, Path] = {}
    peaks: dict[str, list[float]] = {key: [] for key in WORDS}
    for clip in plan():
        wav = work / clip.name.replace(".mp3", ".wav")
        _ffmpeg(work / f"raw_{clip.word}.wav", wav, f"{_pitch(clip.factor)}{TRIM},{FORMAT}")
        staged[clip.name] = wav
        peaks[clip.word].append(peak_db(wav))

    out_dir.mkdir(parents=True, exist_ok=True)
    for clip in plan():
        gain = gain_db(peaks[clip.word], CEILING_DB)
        _ffmpeg(staged[clip.name], out_dir / clip.name, f"volume={gain:.2f}dB", *MP3)


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
