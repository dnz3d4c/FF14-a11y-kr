"""출력 인코딩을 세우는 부분의 검사.

첫 CI 실행이 여기서 죽었다. 윈도 러너의 파이썬 stdout이 cp1252라, 우리 도구가 한국어를
내는 순간 charmap 코덱이 못 넘긴다. 조립 단계와 문서 검사 단계가 같은 자리에서 죽었다.

**로컬에서는 안 드러난다.** 이 기계의 콘솔은 다른 인코딩이라 그대로 나간다. 그래서
워크플로에 환경 변수를 넣는 것만으로는 부족하다 - 워크플로 밖에서 누가 돌리면 다시
같은 자리에서 죽는다.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import console


def test_UTF8이_아니면_다시_세운다() -> None:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")

    console.make_utf8(stream)

    assert stream.encoding.lower().replace("-", "") == "utf8"


def test_이미_UTF8이면_안_건드린다() -> None:
    """다시 세우는 것은 버퍼를 갈아 끼우는 일이라 필요할 때만 한다."""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")

    console.make_utf8(stream)

    assert stream.encoding.lower().replace("-", "") == "utf8"


def test_다시_세운_뒤에는_한국어가_나간다() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")

    console.make_utf8(stream)
    stream.write("한국어")
    stream.flush()

    assert raw.getvalue().decode("utf-8") == "한국어"


def test_다시_세울_수_없는_흐름은_그냥_둔다() -> None:
    """버퍼가 없는 흐름(pytest가 갈아 끼운 것 등)에서 터지면 안 된다."""
    console.make_utf8(io.StringIO())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_cp1252_콘솔에서도_도구가_한국어를_낸다() -> None:
    """진입점 넷을 실제로 cp1252 stdout으로 돌린다. 방어가 없으면 여기서 죽는다."""
    root = _repo_root()
    tools = [
        "tools/docs-check/docs_check.py",
        "tools/ci-check/ci_check.py",
    ]
    for tool in tools:
        done = subprocess.run(
            [sys.executable, str(root / tool)],
            cwd=root,
            capture_output=True,
            # 러너가 준 것과 같은 조건을 만든다. PYTHONUTF8도 껐다.
            env={
                **_clean_env(),
                "PYTHONIOENCODING": "cp1252",
                "PYTHONUTF8": "0",
            },
        )
        assert done.returncode == 0, f"{tool}: {done.stderr.decode('utf-8', 'replace')}"
        assert "UnicodeEncodeError" not in done.stderr.decode("utf-8", "replace")


def _clean_env() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
