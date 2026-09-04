"""조립이 손대는 파일을 읽고 쓴다.

## 줄바꿈을 한 가지로 고정한다

앵커는 `\\n`으로 적혀 있다. 원본 트리의 줄바꿈은 받는 사람의 git 설정에 달려 있어서,
`core.autocrlf`가 다른 클론에서는 같은 파일이 CRLF로 나온다. 그대로 두면 앵커가
전부 어긋나고, 실패 문구는 "앵커를 못 찾았다"가 된다. 진짜 앵커가 깨진 것과 구분이
안 되는 실패다.

그래서 읽을 때 LF로 맞추고 LF로 쓴다. 손대는 파일에만 해당한다. 안 건드리는 파일은
복사 단계에서 바이트 그대로 간다.
"""

from __future__ import annotations

from pathlib import Path


def read(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read().replace("\r\n", "\n")


def write(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
