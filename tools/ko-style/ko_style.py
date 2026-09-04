"""문서의 말투가 한 문서 안에서 갈리는 것과, 사용자가 걷어낸 표현이 되살아나는 것을 잡는다.

## 무엇을 막나

**이 저장소는 숫자·용어·발화 문장을 전부 기계로 막는데 문장 품질만 맨몸이었다.**
그래서 같은 지적이 반복해서 왔다 - 옛 저장소에서 2026-08-20에 사용자가
`README.md` 14자리를 직접 고쳤고, 그 직전 턴의 검증 계획에 "문체는 조언용이고
검사기가 없다"고 적어 놓고 그대로 통과시켰다.

조언은 안 지켜진다. 지켜지는 것은 빨개지는 것뿐이다.

## 두 가지만 본다

**오탐이 잡음이 되면 그날로 죽는 장치라 좁게 시작한다.** 문장 품질 전반을
재려 들지 않는다.

- **말투 혼재**(`register`) - 한 문서 안에 습니다체 종결과 한다체 종결이
  섞이면 실패한다. 사용자 문서는 습니다체, 나머지는 한다체다
- **금지 표현**(`banned`) - 사용자가 실제로 걷어낸 표현이 사용자 문서에
  되살아나면 실패한다

**엠대시는 검사하지 않는다.** 이 저장소의 목록 구분자 관례이고, 사용자가
직접 고친 자리에서 하나도 안 건드렸다. 여기 깃발을 꽂으면 오탐이다.

## 말투를 종성으로 가른다

`니다`로 끝나는지만 보면 **`아니다`가 습니다체로 잡힌다.** 실측에서 개발 문서
다섯의 "습니다체" 22건이 전부 그것이었다.

갈림길은 앞 글자의 종성이다. 습니다체 종결은 `-ㅂ니다`뿐이라 `합니다`(합)·
`있습니다`(습)·`입니다`(입)는 종성이 `ㅂ`이고 `아니다`(아)는 없다. 규칙 하나로
정확히 갈린다.

## 임계는 1이다

**소수 말투 한 줄이면 실패한다.** 2 이상으로 두면 "한 줄만 섞인" 상태가
정상으로 통과하고, 그러면 이 검사가 막으려던 바로 그 자리를 놓친다. 이
저장소의 추적 마크다운 스물다섯이 지금 전부 소수 0이라 임계 1이 그대로
통과한다 - 여유가 없어서 1로 잡은 것이 아니라 여유가 있어서 잡았다
(2026-09-04 실측).

세지 않는 것: 코드 블록 안, 인용(`>`), 표 행(`|`), 제목(`#`), 인라인 코드.
명사형 종결(`~함.`)과 해요체는 `다`로 안 끝나므로 애초에 안 잡힌다.

## 금지 표현은 사용자 교정에서만 자란다

**새 항목은 사용자가 실제로 고쳤을 때만 넣고, 넣을 때 `why`에 언제 무엇이
왜 걸렸는지 적는다.** "이것도 안 좋아 보인다"로 채우기 시작하면 목록이
취향이 되고, 취향은 다음 사람이 못 지킨다.

**목록 자체는 여기 없다.** `korean/lexicon.json`의 `doc` 대상이 갖고
`tools/ko-lexicon`이 읽는다. 전에는 같은 규약의 목록이 도구마다 따로 있었고,
그래서 새 판정이 나왔을 때 어디에 넣을지가 안 정해져 있었다.

사용법:
    uv run python tools/ko-style/ko_style.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO / "tools" / "ko-lexicon"))

import ko_lexicon  # noqa: E402 - 위에서 경로를 넣어야 찾는다

#: 사용자가 읽는 문서. 여기만 습니다체이고 금지 표현 검사도 여기만 돈다.
#: 개발 문서에서 `기능 전체`는 정당할 수 있어서 같이 재지 않는다.
#:
#: **루트 `README.md`는 여기 없다.** 옛 저장소에서는 사용자 문서였지만 이
#: 저장소의 것은 저장소 구조를 설명하는 개발 문서이고 한다체다(실측 10곳 전부).
#: 사용자가 읽는 안내는 `docs/korean/` 아래로 갈라져 있다.
#:
#: `tools/notes-check/template.md`는 `tools/` 아래 있지만 **사용자가 읽을
#: 릴리스 노트의 본**이라 여기 든다. 넣지 않으면 본을 만든 커밋에서 바로
#: 빨개진다 - 이 검사는 추적 마크다운 전부를 훑는다.
USER_DOCS = frozenset(
    {
        "docs/korean/README.ko.md",
        "docs/korean/keys.md",
        "tools/notes-check/template.md",
    }
)

#: 사용자 문서인데 **판마다 늘어나는** 자리. 위 `USER_DOCS`는 정확 경로
#: 집합이라 파일이 생길 때마다 손으로 등록해야 하는데, 릴리스 노트는 발행할
#: 때마다 하나씩 는다. 등록을 잊으면 그 노트가 한다체 문서로 판정돼
#: 습니다체 한 줄에 바로 빨개진다(`MIXED_LIMIT = 1`).
#:
#: **`docs/release-notes/README.md`는 여기서 새어 나간다.** 그 파일은 노트가
#: 아니라 노트를 어떻게 두는지 정하는 개발 문서라 한다체다. 판 번호 이름만
#: 노트이므로 이름으로 가른다.
USER_DOC_PREFIXES = ("docs/release-notes/",)

#: 훑지 않는 자리. 원본 트리는 독일어·영어라 우리 문체가 아니고, `build/`는
#: 조립 산출물이다. `pyproject.toml`의 ruff `extend-exclude`와 같은 둘이다.
#:
#: `upstream/`은 지금 서브모듈이라 `git ls-files`가 안쪽 파일을 안 낸다.
#: 그래도 적어 두는 것은 **문체 판정 대상이 아니라는 뜻이 담기기 때문**이고,
#: 원본 파일이 트리로 들어오는 날 이 줄이 이미 서 있게 된다.
SKIP_PREFIXES = ("upstream/", "build/")


def is_user_doc(rel: str) -> bool:
    """사용자가 읽는 문서인가. 정확 경로와 노트 이름을 둘 다 본다.

    노트 이름 규약은 `ko_lexicon.NOTE_NAME`이 갖는다 - 사본을 두면 규약이
    바뀔 때 한쪽만 따라오고, 못 따라온 쪽은 조용히 통과한다.
    """
    if rel in USER_DOCS:
        return True
    if not rel.startswith(USER_DOC_PREFIXES):
        return False
    return ko_lexicon.NOTE_NAME.match(Path(rel).stem) is not None


#: 소수 말투가 이만큼 나오면 실패한다. 위 `## 임계는 1이다` 참고.
MIXED_LIMIT = 1

#: (표현, 대신 쓸 것, 왜). **사용자가 실제로 고친 것만 들어간다.**
#:
#: 목록의 원천은 `korean/lexicon.json`의 `doc` 대상이다. 새 판정은 거기
#: 넣는다 - 여기 손으로 더하면 대상 셋 중 문서만 아는 판정이 다시 생긴다.
BANNED: tuple[tuple[str, str, str], ...] = ko_lexicon.triples("doc")

_FENCE = re.compile(r"^\s*```")
_INLINE_CODE = re.compile(r"`[^`]*`")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_TAIL = re.compile(r"([가-힣]+)$")
_SENTENCE = re.compile(r"[.!?]\s|[.!?]$")

_FINAL_B = 17  # 유니코드 한글 종성 인덱스에서 `ㅂ`


def _has_final_b(char: str) -> bool:
    """한글 음절의 종성이 `ㅂ`인가. 습니다체를 `아니다`와 가르는 유일한 신호다."""
    if not ("가" <= char <= "힣"):
        return False
    return (ord(char) - 0xAC00) % 28 == _FINAL_B


def register_of(word: str) -> str | None:
    """어절 하나의 말투. 종결이 아니면 `None`."""
    if not word.endswith("다"):
        return None
    if len(word) >= 3 and word[-2] == "니" and _has_final_b(word[-3]):
        return "습니다체"
    return "한다체"


def endings(text: str) -> list[tuple[int, str]]:
    """문서에서 읽은 `(줄 번호, 말투)`. 코드 블록·인용·표·제목은 건너뛴다."""
    found: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith((">", "|", "#")):
            continue
        # 인라인 코드는 명령어·키 이름이라 문장이 아니고, 링크는 주소가
        # 한글 종결처럼 보일 수 있어 글자만 남긴다.
        cleaned = _INLINE_CODE.sub(" ", stripped)
        cleaned = _LINK.sub(r"\1", cleaned).replace("*", "")
        for part in _SENTENCE.split(cleaned):
            part = part.strip().rstrip(".!?")
            tail = _TAIL.search(part)
            if not tail:
                continue
            found_register = register_of(tail.group(1))
            if found_register:
                found.append((number, found_register))
    return found


def tracked_docs(repo: Path = REPO) -> list[str]:
    """git이 추적하는 마크다운. 추적 밖(`dist/`의 배포 사본)은 생성물이라 안 본다."""
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files가 실패했다: {result.stderr.strip()}")
    return [rel for rel in result.stdout.splitlines() if rel and not rel.startswith(SKIP_PREFIXES)]


def check_register(repo: Path = REPO) -> list[str]:
    """한 문서 안에서 말투가 갈리는 자리."""
    problems: list[str] = []
    for rel in tracked_docs(repo):
        path = repo / rel
        if not path.is_file():
            continue
        found = endings(path.read_text(encoding="utf-8"))
        if not found:
            continue
        want = "습니다체" if is_user_doc(rel) else "한다체"
        other = "한다체" if want == "습니다체" else "습니다체"
        strays = [number for number, kind in found if kind == other]
        if len(strays) >= MIXED_LIMIT:
            lines = ", ".join(str(n) for n in strays[:6])
            more = f" 외 {len(strays) - 6}곳" if len(strays) > 6 else ""
            problems.append(
                f"{rel}: {want} 문서인데 {other}가 {len(strays)}곳이다 ({lines}{more}행)"
            )
    return problems


def check_banned(repo: Path = REPO) -> list[str]:
    """사용자가 걷어낸 표현이 사용자 문서에 되살아난 자리.

    **인라인 코드는 안 본다.** 사용 안내가 백틱으로 감싸는 것은 설치
    프로그램과 모드가 실제로 말하는 문장이라, 여기서 고치면 문서가 실물과
    어긋난다. 옛 저장소에서 2026-08-19에 정확히 그 실수를 했다 - 사용자가
    가리키던 것은 문서가 아니라 실물이었는데 문서를 되돌렸다. 실물 문구는
    `tools/loc-check`가 갖는다.
    """
    problems: list[str] = []
    for rel in sorted(USER_DOCS):
        path = repo / rel
        if not path.is_file():
            problems.append(f"{rel}: 파일이 없다 - USER_DOCS를 고쳐라")
            continue
        lines = [
            _INLINE_CODE.sub(" ", line) for line in path.read_text(encoding="utf-8").splitlines()
        ]
        for phrase, instead, why in BANNED:
            for number, line in enumerate(lines, 1):
                if phrase in line:
                    fix = f" -> `{instead}`" if instead else " -> 지운다"
                    problems.append(f"{rel}:{number}: `{phrase}`{fix} ({why})")
    return problems


def check_banned_entries() -> list[str]:
    """목록 자체의 위생. `why`가 비면 다음 사람이 그 줄을 근거 없이 믿는다.

    **대상 셋을 다 본다.** 목록이 한 파일이라 위생도 하나다 - 문서 대상만
    보면 발화나 노트 쪽의 빈 `why`가 여기서도 저기서도 안 걸린다.
    """
    return ko_lexicon.check_entries()


def main(argv: list[str]) -> int:
    problems = check_banned_entries() + check_register() + check_banned()
    if problems:
        print("문서 문체가 어긋난다:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    docs = len(tracked_docs())
    print(
        f"통과 - 문서 {docs}개의 말투가 갈리지 않고, "
        f"걷어낸 표현 {len(BANNED)}개가 되살아나지 않았다"
    )
    print("  이 검사는 말투와 표현 목록만 본다. 문장 품질 전반은 안 본다 -")
    print("  좁게 시작해야 오탐으로 죽지 않는다. 목록은 사용자 교정에서만 자란다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
