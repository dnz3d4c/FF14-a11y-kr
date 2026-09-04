"""화면으로 나가는 글의 인코딩을 세운다.

## 왜 필요한가

우리 도구는 한국어로 보고한다. 그런데 윈도 러너의 파이썬 stdout은 cp1252라, 첫 한국어
한 글자에서 charmap 코덱이 못 넘기고 `UnicodeEncodeError`로 죽는다. 첫 CI 실행이 그렇게
죽었고, 조립 단계와 문서 검사 단계가 같은 자리에서 걸렸다.

**로컬에서는 안 드러난다.** 개발 기계의 콘솔은 인코딩이 달라 그대로 나간다. 그래서
이것은 코드를 읽어서는 못 찾고 실제 러너에서만 나타나는 부류다.

## 왜 워크플로의 환경 변수만으로는 모자란가

워크플로에 `PYTHONIOENCODING`과 `PYTHONUTF8`을 넣어 두었고 `tools/ci-check`가 그것을
지킨다. 그것은 CI 안에서만 도는 방어다. 사람이 손으로 도구를 부르거나 다른 자동화가
부르면 같은 자리에서 다시 죽는다. **도구가 자기 출력을 스스로 책임진다.**

## 왜 다시 세우기인가

인코딩을 못 넘기는 글자를 물음표로 바꾸는 길(`errors="replace"`)도 있는데, 그러면
한국어 보고가 물음표 줄이 되어 조용히 쓸모를 잃는다. 실제로 원본 v5.95의
`YesNoLabels`가 그렇게 망가진 채로 배포되어 있다. 죽지도 않고 읽히지도 않는 것이
제일 나쁘다. 그래서 흐름 자체를 UTF-8로 다시 세운다.
"""

from __future__ import annotations

import sys
from typing import Any


def _is_utf8(stream: Any) -> bool:
    return (getattr(stream, "encoding", "") or "").lower().replace("-", "") == "utf8"


def make_utf8(stream: Any) -> None:
    """흐름이 UTF-8이 아니면 다시 세운다.

    이미 UTF-8이면 손대지 않는다. 다시 세우는 것은 버퍼를 갈아 끼우는 일이라 필요할
    때만 한다. 갈아 끼울 수 없는 흐름(검사가 넣은 `StringIO` 등)은 그냥 둔다 - 인코딩을
    세우다가 도구가 죽으면 원래 막으려던 것보다 나쁘다.
    """
    if _is_utf8(stream):
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError):
        pass


def setup() -> None:
    """진입점 맨 앞에서 부른다. 보고와 오류가 둘 다 한국어로 나간다."""
    make_utf8(sys.stdout)
    make_utf8(sys.stderr)
