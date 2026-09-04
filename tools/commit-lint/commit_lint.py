"""커밋 메시지의 `Release-Note:` 줄이 사용자가 읽을 문장인지 본다.

## 왜 이 저장소에 있나

**같은 문자열이 두 곳에 나온다.** 커밋 트레일러 한 줄과 릴리스 노트의 변경 항목
한 줄은 글자가 같다 - 노트를 쓸 때 트레일러를 그대로 옮기기 때문이다. 규칙을
두 벌로 두면 한쪽만 고쳐지고, 그러면 트레일러를 통과한 문장이 노트에서 걸린다.

그래서 문법은 여기 하나만 두고 `tools/notes-check`가 N7·N14에서 그대로 부른다.

## 옛 저장소에서 뭘 안 가져왔나

원래 이 도구는 커밋 규칙 C1~C14를 재는 468줄짜리였다. **그 규칙 대부분이 옛
저장소의 구조 전용이었다** - 갈래 접두(`[업스트림]`·`[한국전용]`), `vendor/`
포인터를 옮길 수 있는 갈래, 현황판을 같이 고쳤나, `overlay/` 경로와 갈래의
충돌. 이 저장소에는 `vendor/`도 `overlay/`도 없고 갈래 규칙을 정하는 문서도
없어서, 그대로 옮기면 가리키는 것이 없는 규칙이 대부분이 된다.

**남긴 것은 노트 줄 문법 하나다.** 그 규칙은 여기서도 살아 있다 - 이 저장소의
커밋 39개가 전부 `Release-Note:`를 쓰고 있다.

## 이 저장소에 아직 없는 것

**커밋 훅이 없다.** `.git/hooks`가 비어 있고 `core.hooksPath`도 안 걸려 있다.
그래서 이 검사기는 지금 손으로만 돈다.

**어느 커밋이 이 줄을 반드시 남겨야 하는지를 정하는 규칙도 없다.** 옛 저장소는
경로로 물었는데(`overlay/ko/ko.json`을 건드리면 요구) 그 경로가 여기 없다.
그래서 **줄이 있을 때 그 줄이 규칙에 맞나만 본다.** 없는 줄을 요구하지 않는다.

사용법:
    uv run python tools/commit-lint/commit_lint.py <커밋메시지파일>
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: 릴리스 노트로 옮길 한 줄. **제목과 독자가 다르다** - 제목은 여섯 달 뒤에
#: `git log --oneline`으로 커밋을 찾는 사람이 읽고, 이 줄은 새 판을 받은
#: 사람이 읽는다. 한 줄에 둘을 담으려니 판마다 한쪽이 졌고, 노트를 쓸 때마다
#: 커밋 본문을 다시 읽어야 했다.
NOTE_TRAILER = "Release-Note"

#: 노트를 안 남기는 이유를 밝히는 값. 뒤에 이유가 붙어야 한다.
NOTE_EXEMPT_PREFIX = "없음"

#: 노트 줄이 끝나야 하는 꼴을 안내할 때 드는 예. **재는 것은 이 글자가 아니라
#: 종결어미가 아닌 것이다**(아래 `_is_nominal`). `함.`만 받던 때 `~고침.`으로 끝나는
#: 트레일러가 이미 이력에 있었고, 그러면 어미를 규칙에 맞추려고 억지로 바꾸게 된다.
NOTE_SUFFIX = "함."

#: 노트 줄을 끝맺으면 안 되는 글자. **재는 방향을 2026-08-28에 뒤집었다**.
#: 그전에는 명사형 어미 `-ㅁ/음`의 종성 `ㅁ`을 요구했는데, 사용자가 `v5.93.0.2`
#: 노트를 직접 고치며 쓴 `삭제.`·`유지.`가 그 그물에 걸렸다. 규칙이 거르려던 것은
#: 제목의 `~한다`체와 존댓말이고 받침 없는 서술성 명사는 그 대상이 아니다.
#: 그래서 허용을 열거하는 대신 **종결어미만 막는다.**
#:
#: `지`는 종결어미(`하지.`)이기도 하지만 `유지.`가 통과해야 해서 못 넣는다.
#: `라`·`자`도 뺐다 - 명령형·청유형은 노트에 나올 일이 없고 `사용자.` 같은
#: 명사와 부딪히는 쪽이 실제 위험이다.
_TERMINAL_ENDINGS = frozenset("다요죠까네")

#: 노트 줄에 쓰지 않는 말. 사용자 화면 어디에도 안 뜨는 내부 이름이다.
#: 백틱으로 감싼 자리는 안 본다 - 사용자가 직접 실행하는 파일 이름은
#: 노트에 나오는 것이 맞다(`FF14AccessibilityInstaller-KR.exe`).
#: 목록이 규칙의 전부고, 오탐이 나면 여기서 뺀다.
NOTE_BANNED = (
    "Launcher",
    "Installer",
    "csproj",
    "pack-check",
    "release-manifest",
    "commit-lint",
    "KrProfile",
    "Dalamud",
    "repo.json",
    "installer.json",
)

#: 백틱으로 감싼 자리. 노트 줄에서 내부 이름을 찾을 때 먼저 걷어낸다.
#: `notes_check`가 N12·N20에서도 이것을 그대로 쓴다.
_BACKTICK_RE = re.compile(r"`[^`]*`")

#: git이 커밋할 때 지우는 가위선. 아래는 diff 미리보기라 검사 대상이 아니다.
_SCISSORS_RE = re.compile(r"^#\s*-+\s*>8\s*-+")

#: `없음 - <이유>`. 구분자를 요구하는 이유는 `없음주석만 고침`처럼 붙여 쓴 값이
#: 이유를 댄 것으로 통과하면 규칙과 검사가 어긋나서다.
_NOTE_EXEMPT_RE = re.compile(rf"^{NOTE_EXEMPT_PREFIX}\s*-\s*\S")


@dataclass(frozen=True)
class Violation:
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def strip_comments(message: str) -> str:
    """git이 커밋 시 지우는 부분을 미리 지운다."""
    lines: list[str] = []
    for line in message.splitlines():
        if _SCISSORS_RE.match(line):
            break
        if line.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def trailer_value(message: str, key: str) -> str | None:
    """트레일러 값을 돌려준다. 없으면 None.

    git 관행대로 마지막에 나온 것을 채택한다.
    """
    found: str | None = None
    for line in message.splitlines():
        prefix = f"{key}:"
        if line.startswith(prefix):
            found = line[len(prefix) :].strip()
    return found


def _is_nominal(note: str) -> bool:
    """명사형 종결인가. 한글 한 글자에 마침표가 붙고 그 글자가 종결어미가 아닌 꼴이다.

    `함.`·`고침.`·`바꿈.`·`삭제.`·`유지.`가 통과하고 `한다.`·`합니다.`는 안 된다.
    마침표를 같이 요구하는 것은 `~하도록 함`처럼 끝을 안 맺은 줄을 거르기 위해서다.

    **마침표 앞의 공백은 무시한다.** `출력함 .`은 사용자가 준 문안 그대로이고,
    공백 하나가 종결 판정을 뒤집는 것은 규칙이 재려던 것과 상관없다.
    """
    if not note.endswith("."):
        return False
    stem = note[:-1].rstrip()
    if not stem:
        return False
    last = stem[-1]
    return "가" <= last <= "힣" and last not in _TERMINAL_ENDINGS


def note_problem(note: str | None) -> str | None:
    """릴리스 노트 줄의 문제. 없으면 None."""
    if not note:
        return (
            "사용자가 받는 것이 바뀌었다. 릴리스 노트로 그대로 옮길 한 줄을 "
            f"남겨라 - 예: `{NOTE_TRAILER}: 바탕화면 바로가기로 게임과 "
            "KR 달라무드 업데이터가 실행되도록 함.` "
            f"사용자에게 안 닿는 변경이면 `{NOTE_TRAILER}: 없음 - <이유>`"
        )

    if note.startswith(NOTE_EXEMPT_PREFIX):
        if not _NOTE_EXEMPT_RE.match(note):
            return (
                f"`{NOTE_TRAILER}: {NOTE_EXEMPT_PREFIX} - <이유>` 꼴로 이유를 대라 - "
                "예: `없음 - 주석만 고침`. 값이 비면 면제가 아니다"
            )
        return None

    if not _is_nominal(note):
        return (
            "노트 줄은 사용자가 읽을 문장 그대로다. "
            f"`~하도록 {NOTE_SUFFIX}`처럼 명사형에 마침표를 붙여 끝내라 - "
            "제목의 `~한다`와 독자가 다르다"
        )

    banned = [word for word in NOTE_BANNED if word in _BACKTICK_RE.sub("", note)]
    if banned:
        return (
            f"노트 줄에 내부 이름을 쓰지 않는다: {', '.join(banned)}. "
            "사용자 화면에 뜨는 이름으로 바꿔라 - 사용자가 보는 것은 "
            "`Launcher`가 아니라 `바탕화면 바로가기`다. "
            "직접 실행하는 파일 이름이면 백틱으로 감싼다"
        )

    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("사용법: commit_lint.py <커밋메시지파일>", file=sys.stderr)
        return 2

    body = strip_comments(Path(argv[1]).read_text(encoding="utf-8"))
    value = trailer_value(body, NOTE_TRAILER)

    # **없는 줄을 요구하지 않는다.** 어느 커밋이 이 줄을 반드시 남겨야 하는지를
    # 정하는 규칙이 이 저장소에 아직 없어서다. 대신 **잰 것이 없다는 것을
    # 화면에 남긴다** - 조용히 0으로 끝나면 통과한 것과 안 잰 것이 같아진다.
    if value is None:
        print(f"검사할 것이 없다 - `{NOTE_TRAILER}:` 줄이 이 메시지에 없다")
        print("  어느 커밋이 이 줄을 남겨야 하는지를 정하는 규칙은 이 저장소에 아직 없다.")
        return 0

    problem = note_problem(value)
    if problem is None:
        print(f"통과 - `{NOTE_TRAILER}: {value}`")
        return 0

    print(f"`{NOTE_TRAILER}` 줄이 규칙에 안 맞는다:", file=sys.stderr)
    print(f"  {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
