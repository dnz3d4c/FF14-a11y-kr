"""릴리스 노트 본문이 판마다 다르게 쓰이는 것을 막는다.

## 무엇을 막나

**노트 본문을 만드는 코드도 본도 없었다.** 옛 저장소는 사람이 배포 폴더에
손으로 쓰고 그대로 올렸는데, 그 폴더가 `.gitignore`에 있어 **본문이 판마다
사라졌다** - `git log --all -- '*release-notes*'`가 0건이었다. 다음 판을 쓸 때
이전 판을 볼 수 없으니 매번 새로 지어냈고, 그래서 `v5.88.0.0`과 `v5.88.0.1`의
절 이름과 종결형이 이미 서로 달랐다.

**이 저장소는 노트를 `docs/release-notes/`에 둔다.** 파일 하나가 판 하나이고
이름이 판 번호다. 규약은 `docs/release-notes/README.md`가 갖는다.

커밋 트레일러 한 줄(`Release-Note:`)의 문법은 `commit_lint`가 갖는다. 그 줄들을
모아 **노트 전체를 조립하는 단계**에 소유자가 없었고, 이 검사기가 그 자리다.

기계가 재는 규칙 N1~N26의 명세는 `docs/dev/release-notes-rules.md`가 갖는다.
**여기 베끼지 않는다** - `--rules`가 그 문서를 읽어 목록을 내고, 문서에 있는
번호와 이 파일이 실제로 내는 번호가 어긋나면 같이 말한다.

문체와 판정 기준은 `ko-release-notes` 스킬이 갖는다.

## 규칙 접두가 `N`인 이유

커밋 검사기의 규칙과 코드 공간을 섞지 않는다. 섞으면 어느 문서를 봐야 하는지
번호만으로 못 가른다.

## 기계가 못 보는 것

**`모드 변경사항:` 줄의 진위는 판정 불가가 확정이다.** 세 갈래가 다 막힌다 -
판 번호는 설치 프로그램만 고친 판에서도 오르고(v5.88.0.1이 그 실물), 산출물
바이트는 판 번호가 zip 안 매니페스트에 들어가는 데다 DLL의 MVID가 빌드마다
바뀌며, 원본 핀은 판 올림만 하는 커밋도 움직인다. 그래서 이 검사기는 **줄의
꼴만** 보고 진위는 안 본다.

**그 줄의 위치도 판정 불가로 넘겼다.** 위에 항목이 없는 모양은 두 상황이
같다 - 모드만 바뀐 판과 순서를 잘못 둔 판이다. 앞엣것이 실물로 나오면서
(`v5.91.0.1`) 뒤엣것을 잡던 검사를 풀었다.

나머지도 문서가 갖는다 - 산문 절의 도입 문단, 변경 항목의 순서와 취사,
강조 한 번을 어디에 쓸까, 제한사항이 현황과 맞나, 문장이 사실인가.

## 언제 도나

`docs/dev/release-notes-rules.md`의 "언제 도나" 절은 이번 판 노트를
스테이징하면 커밋 훅에서도 돈다고 정한다. **이 저장소에는 그 훅이 없다** -
`.git/hooks`가 비어 있고 `core.hooksPath`도 안 걸려 있다. `--current-only`가
그 훅이 쓸 자리이고 지금은 아무도 안 부른다.

사용법:
    uv run python tools/notes-check/notes_check.py --rules
    uv run python tools/notes-check/notes_check.py
    uv run python tools/notes-check/notes_check.py docs/release-notes/5.95.0.0.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# 같은 일을 두 번 만들지 않는다. 특히 `note_problem`은 **트레일러와 노트 항목이
# 같은 문자열**이라서, 그대로 부르면 규칙이 저절로 같아진다.
for _sibling in ("commit-lint", "ko-style", "ko-lexicon", "release-manifest"):
    sys.path.insert(0, str(REPO / "tools" / _sibling))

import commit_lint  # noqa: E402 - 위에서 경로를 넣어야 찾는다
import ko_lexicon  # noqa: E402
import ko_style  # noqa: E402
import release_manifest  # noqa: E402

Violation = commit_lint.Violation

#: 노트가 사는 곳. **파일 하나가 판 하나이고 이름이 판 번호다.**
#: 규약은 `docs/release-notes/README.md`가 갖는다.
NOTES_DIR = ko_lexicon.NOTES_DIR

#: 기계가 재는 규칙의 명세. `--rules`가 여기서 목록을 읽는다.
RULES_DOC = REPO / "docs" / "dev" / "release-notes-rules.md"

#: 판 번호 꼴의 파일 이름. 네 마디다. **`ko_lexicon`이 갖는다** - 세 도구가
#: 다 "어느 파일이 노트인가"를 알아야 하는데 사본을 두면 규약이 바뀔 때
#: 못 따라온 쪽이 노트를 하나도 못 찾은 채 조용히 통과한다.
_VERSION_NAME = ko_lexicon.NOTE_NAME

#: 명세 문서의 표 한 줄. `| N1 | 무엇을 보나 |` 꼴이다.
_RULE_ROW = re.compile(r"^\|\s*(N\d+)\s*\|\s*(.+?)\s*\|\s*$")

#: 이 파일이 실제로 내는 규칙 번호를 긁는 꼴. **선언 목록을 따로 두지 않는다** -
#: 그러면 명세가 문서·선언·코드 세 벌이 되고 셋이 갈린다.
_EMITTED_CODE = re.compile(r'Violation\(\s*"(N\d+)"')


def note_paths(notes_dir: Path | None = None) -> tuple[Path, ...]:
    """판 번호 이름을 가진 노트 전부. `README.md`는 노트가 아니라 규약 문서다.

    고르는 규칙은 `ko_lexicon`이 갖는다. 여기서 다시 만들면 두 도구가 서로
    다른 파일 집합을 노트라고 부르게 된다.
    """
    return ko_lexicon.note_paths(NOTES_DIR if notes_dir is None else notes_dir)


def current_version(notes_dir: Path | None = None) -> str | None:
    """이번 판. 노트 중 판 번호가 제일 높은 것이다.

    **산출물을 안 읽는다.** 갓 클론한 자리에는 배포물이 없어서, 거기서
    이번 판을 읽으면 부르는 쪽이 통째로 죽는다. 노트 파일은 저장소 안에 있다.
    """
    found = note_paths(notes_dir)
    return found[-1].stem if found else None


def rules(path: Path | None = None) -> tuple[tuple[str, str], ...]:
    """명세 문서가 정한 `(번호, 무엇을 보나)`. **여기서 지어내지 않는다.**"""
    path = RULES_DOC if path is None else path
    found: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = _RULE_ROW.match(line)
        if row is not None:
            found.append((row.group(1), row.group(2)))
    return tuple(found)


def emitted_codes(path: Path | None = None) -> frozenset[str]:
    """이 검사기가 실제로 내는 규칙 번호. 자기 소스에서 긁는다."""
    path = Path(__file__) if path is None else path
    return frozenset(_EMITTED_CODE.findall(path.read_text(encoding="utf-8")))


def rule_gaps(path: Path | None = None) -> list[str]:
    """명세와 구현이 갈린 자리. **비어 있어야 명세가 한 벌이다.**"""
    listed = {code for code, _ in rules(path)}
    emitted = emitted_codes()
    problems: list[str] = []
    if listed - emitted:
        missing = ", ".join(sorted(listed - emitted))
        problems.append(f"문서에 있는데 검사기가 안 내는 번호: {missing}")
    if emitted - listed:
        extra = ", ".join(sorted(emitted - listed))
        problems.append(f"검사기가 내는데 문서에 없는 번호: {extra}")
    return problems


#: 본. 판마다 여기서 떠서 쓴다.
TEMPLATE_PATH = Path(__file__).resolve().parent / "template.md"

#: 절 이름과 순서. **열거 밖은 통과가 아니라 위반이다** - 이슈 링크 절이
#: 실제로 그렇게 되살아났고, "모르는 절은 그냥 둔다"로 두면 다시 그렇게 된다.
CHANGES_SECTION = "v{version} 변경사항"

#: 원본 개발자가 스스로 미검증이라고 밝힌 것만 담는 절. **전에는 우리 결함과
#: 한 목록에 섞여 있었다** - 듣는 사람이 "고칠 쪽이 우리인가 원본인가"를 못
#: 갈랐다. 우리 것은 `알려진 제한사항`에 남는다.
UNVERIFIED_SECTION = "모드 개발자가 검증하지 못한 것"

SECTION_NAMES = (
    "설치",
    CHANGES_SECTION,
    "준비물",
    "업데이트 방법",
    "알려진 제한사항",
    UNVERIFIED_SECTION,
    "라이선스",
)

#: 제목 바로 아래가 목록이어야 하는 절. "도입 문단을 넣지 않는다"를 기계가
#: 잴 수 있게 좁힌 판이다 - 절 전체의 산문 여부는 안 본다.
LIST_SECTIONS = (CHANGES_SECTION, "준비물", "알려진 제한사항", UNVERIFIED_SECTION)

#: 모드가 바뀌었는지 알리는 줄. **분류가 아니라 받는 방법을 가르는 신호다** -
#: 모드가 바뀌면 게임을 켤 때 Dalamud가 자동으로 갱신하고, 안 바뀌면 사용자가
#: 설치 프로그램을 다시 돌려야 한다.
MOD_PREFIX = "모드 변경사항:"
MOD_NONE = "없음."

#: 한국어 안내 문장만 고친 것을 담는 표지.
#:
#: **`모드 변경사항:`과 축이 다르다.** 그 줄은 받는 방법을 가르고, 이 줄은
#: **원본 모드가 바뀌었나**를 가른다. 받는 방법으로는 둘이 같은 편이다 -
#: 한국어 문장도 플러그인 안에 있어서 게임을 켜면 Dalamud가 준다.
#:
#: 갈라 놓지 않으면 한국어만 고친 판이 `모드 변경사항:` 아래로 들어가고,
#: 듣는 사람은 원본 모드가 바뀐 것으로 읽는다. `v5.91.0.1`이 그렇게 나갔다.
KO_PREFIX = "한국어 번역 문장 수정:"

#: 보충 표기. 공식 가이드가 쓰는 꼴이고 노트에서는 자산 안내 한 줄이다.
NOTE_MARK = "※"

#: 릴리스에서 걷어낸 자산과 그 자리에 올 것(N20). **목록이 규칙의 전부다** -
#: N18과 같은 방식이고, 오탐이 나면 빼면 된다.
#:
#: **노트는 사람이 본을 복사해 쓰는 자리라 옛 판 문구가 그대로 따라온다.**
#: 그러면 받는 사람은 릴리스 페이지에서 그 이름을 영영 못 찾는데, 검사는
#: 통과하므로 내는 사람 화면에는 아무 일도 안 일어난다. 셋 다 옛 저장소의
#: 노트에 실제로 적혀 있던 이름이고, 이 저장소의 릴리스 자산은
#: `release_manifest.RELEASE_ASSETS` 넷뿐이라 여전히 없는 이름이다.
DROPPED_ASSETS = {
    "FF14Accessibility-KR-Setup.zip": (
        f"묶음 압축은 안 낸다. 사람이 받는 것은 `{release_manifest.INSTALLER_NAME}` 하나다"
    ),
    "README.ko.md": f"문서는 자산이 아니라 주소로 준다: {release_manifest.GUIDE_DOC_URL}",
    "KEYS.ko.md": f"문서는 자산이 아니라 주소로 준다: {release_manifest.KEYS_DOC_URL}",
}

#: 백틱 안에 한글을 써도 되는 것. **지금은 하나도 없다.**
#:
#: 릴리스에 올라가는 이름은 전부 ASCII다(`gh`가 윈도에서 한글 자산 이름을
#: 삼킨다). 배포 폴더 안에서는 문서 둘이 한글 이름을 갖지만
#: (`release_manifest.GUIDE_NAME`·`KEYS_NAME`) 그것은 릴리스 자산이 아니라
#: 폴더 안의 이름이라, **노트에 그 이름을 쓰면 받는 사람이 릴리스 페이지에서
#: 못 찾는다.**
BACKTICK_HANGUL_OK: tuple[str, ...] = ()

#: 노트에 쓰면 안 되는 한국어 낱말과 그 자리에 쓸 것(N18).
#:
#: **목록이 규칙의 전부다.** 소리로 갈리는 것을 일반 규칙으로 잡을 방법이
#: 없고, 모드가 무엇으로 발화하는지도 기계가 문맥에서 못 고른다. 그래서
#: 겪은 자리만 넣고 오탐이 나면 뺀다.
#:
#: **목록 자체는 여기 없다.** `korean/lexicon.json`의 `note` 대상이 갖는다.
#: 전에는 같은 규약의 목록이 도구마다 따로 있어서, 사용자 교정이 나왔을 때
#: 어디에 넣을지가 안 정해져 있었다 - `v5.93.0.2` 교정의 낱말 판정이 문서 표에만
#: 남았고 `v5.94.0.0`에서 되돌아갔다.
#: 값은 `대신 쓸 것 - 왜`다. 대체어만 주면 왜 그런지가 화면에서 사라지고,
#: 그러면 다음 사람이 판정을 근거 없이 믿거나 근거 없이 뒤집는다.
NOTE_KO_BANNED = {
    entry.bad: (f"{entry.good} - {entry.why}" if entry.good else entry.why)
    for entry in ko_lexicon.entries("note")
}

#: 변경 항목이 **모드가 내는 소리**를 서술할 때 쓰지 않는 말과 대체어(N24).
#:
#: `v5.93.0.2`에서 사용자가 `말한다`를 `음성 출력`으로 고쳤고 그 판정이 문서
#: 표에 박혔는데, **`v5.94.0.0`에서 열두 자리가 되돌아갔다.** 그 표는 사람이
#: 훑는 자리라 다섯 판 연속으로 안 훑였다.
#:
#: **전에는 이것을 못 잰다고 적어 뒀다.** "`말함`은 살아 있는 자리가 있어서
#: 목록에 넣으면 오탐"이라고 했는데, 바로 앞 문단이 그 경계를 이미 정의했다 -
#: **인용하는 자리의 `~라고 말함`만 살아 있다.** 낱말 단위로 가를 수 있고,
#: 아래 정규식이 그 하나만 비켜 간다.
#:
#: 활용형을 따로 적는 것은 한글이 음절 단위라서다. 어간만 넣으면 실제로 안 걸린다.
NOTE_SPEECH_BANNED = {
    "알려 줌": "음성 출력함",
    "알려 주고": "음성 출력하고",
    "알려 주는데": "음성 출력하는데",
    "알려 주지만": "음성 출력하지만",
    "말함": "음성 출력함",
    "말하고": "음성 출력하고",
    "말하게 됨": "음성 출력하게 됨",
    "말하지 않음": "음성 출력하지 않음",
    "들림": "음성 출력함",
    "들리고": "음성 출력하고",
}

#: 위 말을 잡는 꼴. **`~라고` 뒤는 비켜 간다** - 그 자리는 무엇을 발화하는지
#: 인용하는 것이라 살아 있다(`v5.93.0.1`의 `…놓기라고 말함`을 사용자가 승인).
_SPEECH_BANNED_RE = {
    word: re.compile(rf"(?<!라고 ){re.escape(word)}") for word in NOTE_SPEECH_BANNED
}

#: 변경사항 절에서 목록을 가르는 표지로 쓸 수 있는 줄(N25).
SECTION_MARKS = (KO_PREFIX, MOD_PREFIX)

#: 미검증 절에 지어내면 안 되는 어구(N26).
#:
#: 절 이름이 주체와 조건을 이미 말하므로 줄마다 되풀이하지 않는다. `원본
#: 개발자가 ... 밝혔습니다`를 붙이지 않는 것이 규칙이고, **원문에 없는
#: 어구를 우리가 지어내는 자리이기도 하다.** 사용자가 두 번 지적했고
#: `v5.94.0.0`이 `원본 개발자가 게임에서 확인했다고 밝힘`으로 또 나갔다 -
#: 미검증 절에 검증 진술을 두는 것이라 절 제목과도 모순이다.
#:
#: **종결형 전체를 재지 않는다.** 규칙이 `확인하지 못함.`과 `개발자가 피드백
#: 요청함.` 둘을 정해 뒀지만, 그것은 **꼬리를 뭘로 맺느냐**의 규칙이지 줄이
#: 그 두 문장으로만 끝나야 한다는 뜻이 아니다. 발행본 열하나의 미검증 줄이
#: `아예 없는 것보다 나쁨.`·`설정에서 키를 바꿀 수 있음.`처럼 부연으로 끝나고
#: 그 전부가 정당하다. 둘로 좁히면 나가 있는 판이 통째로 빨개진다.
#:
#: 그래서 겪은 자리만 잡는다. `밝히-`의 활용형은 발행본 열하나에서 0건이다.
_INVENTED_RE = re.compile(r"밝[히혀힌힘혔]")

#: 미검증 절에 쓰는 종결. 위반을 알릴 때 무엇으로 바꾸라고 말하는 자리다.
UNVERIFIED_ENDINGS = ("확인하지 못함.", "개발자가 피드백 요청함.")

#: 위 낱말이 **낱말의 시작일 때만** 잡는 꼴. 뒤는 안 막는다 - 조사가 붙는다.
#:
#: 처음 판이 부분 문자열로 재서 이미 나간 판 둘을 빨갛게 만들었다.
#: `기다리는지`의 `다리`와 `경고가`의 `고가`다. 옛 판을 고치라는 지시를 받고
#: 실물을 열었다가 드러났고, **틀린 것은 옛 판이 아니라 검사기였다.**
_KO_BANNED_RE = {word: re.compile(rf"(?<![가-힣]){re.escape(word)}") for word in NOTE_KO_BANNED}

#: 항목 하나를 통째로 강조한 것으로 세는 비율. **밀도로 재면 사고를 못 잡는다** -
#: 발행본의 강조 밀도 8.5%가 사용자가 쓴 사용 안내의 11.6%보다 낮았다.
#: 실측에서 사용자가 쓴 565줄(항목 202개)에 전면 강조가 0개라 오탐 여지가 없다.
FULL_EMPHASIS_RATIO = 2

#: 한 절에 허용하는 굵게. 기울임은 세 문서 모두 0회라 여는 것 자체가 근거 없다.
BOLD_PER_SECTION = 1

_HEADING = re.compile(r"^(#+)\s+(.*)$")
_ITEM = re.compile(r"^- (.*)$")

#: 항목 안에 다시 나온 목록 표지. **앞에 공백이 없는 것만 잰다** - 문장을 잇는
#: 붙임표(` - `)는 정상이고, 오탐이 잡음이 되면 그날로 죽는 장치라서다.
#: 발행본 다섯과 본에서 0건인 것을 확인하고 넣었다.
_GLUED_ITEM = re.compile(r"\S- ")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"\*([^*]+)\*")
_LINK = re.compile(r"\[[^\]]+\]\([^)]+\)")
_VERSION = re.compile(r"v\d+(?:\.\d+)+")
_PLACEHOLDER = re.compile(r"\{\{([^}]*)\}\}")
_HANGUL = re.compile(r"[가-힣]")
_BACKTICK = commit_lint._BACKTICK_RE  # noqa: SLF001 - 같은 규칙을 두 벌로 두지 않는다


def sections_of(version: str) -> tuple[str, ...]:
    """이번 판의 절 이름. 변경사항 절만 판 번호를 이름에 갖는다."""
    return tuple(name.format(version=version) for name in SECTION_NAMES)


def split_sections(text: str) -> list[tuple[str, list[str]]]:
    """`(절 이름, 본문 줄)`. 첫 항목은 `###` 앞의 서두이고 이름이 빈 문자열이다."""
    found: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        head = _HEADING.match(line)
        if head is not None and len(head.group(1)) == 3:
            found.append((head.group(2).strip(), []))
        else:
            found[-1][1].append(line)
    return found


def placeholders(text: str) -> set[str]:
    """`{{...}}` 자리 이름. `<버전>` 꼴을 안 쓰는 것은 세 문서가 이미 다른 뜻으로 써서다."""
    return set(_PLACEHOLDER.findall(text))


def template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def render(version: str) -> str:
    """본에서 판 번호만 채운다. 나머지 다섯은 사람이 채우고 N6이 안 채운 것을 막는다."""
    return template().replace("{{버전}}", release_manifest.normalize_version(version))


def decode(raw: bytes) -> tuple[str, list[Violation]]:
    """읽은 바이트를 본문으로. BOM은 떼고 알린다.

    BOM이 붙으면 첫 줄이 `## `로 안 시작해 **제목이 본문 글자가 된다.** 그
    상태로 올리면 릴리스 페이지에서 제목 줄만 조용히 문단이 되고, 내는 사람
    화면에는 아무 오류도 안 남는다.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        return "", [
            Violation(
                "N1",
                f"UTF-8로 못 읽는다({error.reason}, {error.start}바이트째). "
                "편집기 인코딩을 UTF-8로 바꿔 다시 저장해라",
            )
        ]

    if text.startswith("﻿"):
        return text.lstrip("﻿"), [
            Violation(
                "N1",
                "맨 앞에 BOM이 있다. 첫 줄이 `## `로 안 시작해 제목이 본문 글자가 된다 - "
                "BOM 없는 UTF-8로 다시 저장해라",
            )
        ]

    return text, []


def _emphasis_len(line: str) -> int:
    """강조 안 글자 수. 굵게와 기울임을 함께 센다."""
    bold = _BOLD.findall(line)
    rest = _BOLD.sub(" ", line)
    return sum(len(t) for t in bold) + sum(len(t) for t in _ITALIC.findall(rest))


def _mod_line_problem(body: list[str]) -> str | None:
    """변경사항 절의 `모드 변경사항:` 줄 문제. 없으면 None.

    **위에 항목이 없는 것은 안 막는다.** 모드만 바뀐 판은 그 줄 위에 둘 항목이
    아예 없어서 여기가 무조건 빨개졌다 - `v5.91.0.1`이 그 실물이고, 그때까지의
    판은 전부 모드와 문서가 같이 바뀌어서 이 모양이 한 번도 안 나왔다.

    **완화하면서 구별 하나를 버린다.** "위에 항목이 없다"는 두 상황이 같은
    모양이다 - 모드만 바뀐 판과 순서를 잘못 둔 판이다. 기계가 못 가르므로
    아래에 목록이 있으면 통과시킨다. 위도 아래도 비었을 때만 여전히 위반이다.
    """
    marks = [i for i, line in enumerate(body) if line.startswith(MOD_PREFIX)]
    if len(marks) != 1:
        return (
            f"`{MOD_PREFIX}` 줄이 {len(marks)}개다. 변경 항목 목록 **뒤에** 하나만 둔다 - "
            f"모드가 안 바뀌었으면 `{MOD_PREFIX} {MOD_NONE}`, 바뀌었으면 "
            f"`{MOD_PREFIX}` 아래에 목록으로 적는다. 받는 방법이 갈리는 자리라 생략하지 않는다"
        )

    at = marks[0]
    before = [line for line in body[:at] if _ITEM.match(line)]
    after = [line for line in body[at + 1 :] if _ITEM.match(line)]
    if not before and not after:
        return (
            f"`{MOD_PREFIX}` 줄만 있고 변경 항목이 위에도 아래에도 없다. "
            "이번 판이 무엇을 바꿨는지를 노트가 한 줄도 안 말한다"
        )

    value = body[at][len(MOD_PREFIX) :].strip()
    if value == MOD_NONE:
        if after:
            return f"`{MOD_PREFIX} {MOD_NONE}`이라고 적고 아래에 항목 {len(after)}개를 뒀다"
        return None
    if value:
        return (
            f"`{MOD_PREFIX} {value}`는 쓰지 않는다. "
            f"`{MOD_PREFIX} {MOD_NONE}`이거나, 값을 비우고 아래에 목록을 적는다"
        )
    if not after:
        return f"`{MOD_PREFIX}` 값이 비었는데 아래에 목록이 없다"
    return None


def _ko_line_problem(body: list[str]) -> str | None:
    """변경사항 절의 `한국어 번역 문장 수정:` 줄 문제. 없으면 None.

    **줄 자체가 선택이다.** 한국어 문장을 안 고친 판에는 안 나온다 - 없는
    것으로 구분이 이미 서므로 `없음.`을 요구하지 않는다. `모드 변경사항:`이
    그것을 요구하는 것은 그쪽이 받는 방법을 가르는 신호라서다.
    """
    marks = [i for i, line in enumerate(body) if line.startswith(KO_PREFIX)]
    if not marks:
        return None
    if len(marks) > 1:
        return f"`{KO_PREFIX}` 줄이 {len(marks)}개다. 있으면 하나만 둔다"

    at = marks[0]
    mod = next((i for i, line in enumerate(body) if line.startswith(MOD_PREFIX)), None)
    if mod is not None and mod < at:
        return (
            f"`{KO_PREFIX}` 줄이 `{MOD_PREFIX}` 줄보다 뒤에 있다. 앞에 둬라 - "
            "받는 방법을 가르는 신호가 절의 마지막에 와야 목록에 안 묻힌다"
        )

    value = body[at][len(KO_PREFIX) :].strip()
    if value:
        return (
            f"`{KO_PREFIX} {value}`는 쓰지 않는다. "
            "값을 비우고 아래에 목록을 적는다. 고친 것이 없으면 줄째로 뺀다"
        )

    rest = body[at + 1 :] if mod is None else body[at + 1 : mod]
    if not [line for line in rest if _ITEM.match(line)]:
        return f"`{KO_PREFIX}` 줄 아래에 목록이 없다. 고친 것이 없으면 줄째로 뺀다"
    return None


def _section_mark_problem(body: list[str]) -> str | None:
    """변경사항 절의 목록 사이에 규칙 밖 표지가 있나. 없으면 None.

    **첫 항목부터 마지막 항목까지만 본다.** 그 뒤에 오는 꼬리 문단(`원본 모드의
    전체 변경 이력은 …`과 그 주소)은 목록을 가르는 표지가 아니라 절의 맺음말이고,
    발행본 전부가 그것을 갖고 있다. 목록 구간 안에 있는 산문 줄만 표지로 읽힌다.

    `v5.94.0.0`이 `한국어판 변경사항은 다음과 같습니다.`를 목록 사이에 새로
    만들었고 **N8·N19·N16 어느 것도 그것을 안 봤다** - 셋 다 자기 표지가 몇 개고
    어디 있는지만 세지, 규칙 밖 표지가 하나 더 생긴 것은 세는 자리가 없었다.
    """
    marks = [i for i, line in enumerate(body) if _ITEM.match(line)]
    if not marks:
        return None

    for line in body[marks[0] : marks[-1] + 1]:
        # 들여쓴 줄은 항목에 딸린 예시나 복사해 넣을 경로다.
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        if _ITEM.match(line) or line.startswith(SECTION_MARKS):
            continue
        return (
            f"변경사항 절의 목록 사이에 표지가 아닌 줄이 있다: {line.strip()[:60]}. "
            f"목록을 가르는 표지는 `{KO_PREFIX}`와 `{MOD_PREFIX}` 둘뿐이다 - "
            "표지를 새로 만들면 듣는 사람이 그 묶음이 무슨 부류인지 규칙 밖에서 "
            "짐작해야 한다"
        )
    return None


def check(text: str, version: str) -> list[Violation]:
    """어긴 것 목록. 비어 있으면 통과."""
    version = release_manifest.normalize_version(version)
    want_sections = sections_of(version)
    parts = split_sections(text)
    lines = text.splitlines()
    bare = _BACKTICK.sub(" ", text)

    violations: list[Violation] = []

    # N2 - 본문에 `##` 제목을 두지 않는다.
    #
    # 한때는 반대였다. "릴리스 페이지 제목과 겹치지만 소리로 본문만 훑을 때
    # 기준점이 되므로 남긴다"고 적혀 있었는데, **그렇게 듣는 당사자가 같은
    # 정보가 두 번 나온다고 판정했다.** 근거를 세운 쪽이 모델이고 뒤집은 쪽이
    # 실제 사용자라, 사용자 판정이 이긴다.
    tops = [line for line in lines if _HEADING.match(line) and line.startswith("## ")]
    if tops:
        violations.append(
            Violation(
                "N2",
                f"`##` 제목이 {len(tops)}개 있다: {tops[0].strip()}. "
                "릴리스 페이지 제목과 같은 정보라 본문에는 두지 않는다 - 절은 전부 `###`다",
            )
        )
    head = next((line for line in lines if line.strip()), "")
    want_head = f"### {want_sections[0]}"
    if head.strip() != want_head:
        violations.append(
            Violation("N2", f"첫 줄이 `{want_head}`여야 한다. 지금은 `{head.strip()}`이다")
        )

    # N3 - 절 구성. **리스트 동등 비교다.** 열거 밖 절은 통과가 아니라 위반이다.
    got_sections = tuple(name for name, _ in parts[1:])
    if got_sections != want_sections:
        message = (
            f"절 구성이 다르다. 있어야 하는 것: {' → '.join(want_sections)}. "
            f"지금: {' → '.join(got_sections) or '(없음)'}"
        )
        if any("문제를 알릴 곳" in name or "이슈" in name for name in got_sections):
            message += ". 이슈 링크 절은 넣지 않는다"
        violations.append(Violation("N3", message))

    # N4 - 제목 깊이. 발행본이 절을 전부 `##`로 쓴 것이 이 규칙이 잡는 실물이다.
    # **개수는 절 목록에서 계산한다** - 여기 숫자를 적으면 절이 늘 때 안 따라온다.
    depths = [len(m.group(1)) for m in (_HEADING.match(line) for line in lines) if m]
    if depths != [3] * len(want_sections):
        violations.append(
            Violation(
                "N4",
                f"제목이 `###` {len(want_sections)}개뿐이어야 한다. 지금 깊이별로 {depths}다",
            )
        )

    # N5 - 지난 판을 복사해 한 자리를 안 고치는 것.
    stale = sorted({v for v in _VERSION.findall(text) if v != f"v{version}"})
    if stale:
        violations.append(
            Violation(
                "N5",
                f"이번 판이 아닌 판 번호가 있다: {', '.join(stale)}. 이번 판은 v{version}이다",
            )
        )

    # N6 - 안 채운 자리.
    left = placeholders(text)
    if left:
        violations.append(
            Violation(
                "N6",
                f"본의 자리표시자가 남아 있다: {', '.join(f'{{{{{n}}}}}' for n in sorted(left))}",
            )
        )

    changes = CHANGES_SECTION.format(version=version)
    body_of = {name: body for name, body in parts[1:]}

    # N7 - 변경 항목. **트레일러와 같은 문자열이라 `note_problem`을 그대로 부른다.**
    # 다만 `없음 - <이유>` 면제는 트레일러의 것이고 노트 항목에서는 안 통한다.
    for line in body_of.get(changes, []):
        item = _ITEM.match(line)
        if item is None or line.startswith(MOD_PREFIX):
            continue
        note = item.group(1).strip()
        if note.startswith(commit_lint.NOTE_EXEMPT_PREFIX):
            violations.append(
                Violation(
                    "N7",
                    f"변경 항목에 `{note}`를 적었다. 트레일러의 면제는 노트 항목에 옮기지 않는다",
                )
            )
            continue
        problem = commit_lint.note_problem(note)
        if problem:
            violations.append(Violation("N7", f"변경 항목 `{note}`: {problem}"))

    # N8 - 받는 방법을 가르는 줄.
    if changes in body_of:
        problem = _mod_line_problem(body_of[changes])
        if problem:
            violations.append(Violation("N8", problem))

    # N19 - 원본 모드가 바뀌었나를 가르는 줄. N8과 축이 다르다.
    if changes in body_of:
        problem = _ko_line_problem(body_of[changes])
        if problem:
            violations.append(Violation("N19", problem))

    # N24 - 모드가 내는 소리를 서술하는 말. **변경 항목만 본다** - 산문 절은
    # 습니다체라 `알려 줍니다`가 정상이고, 범위를 넓히면 그날로 오탐이 된다.
    for line in body_of.get(changes, []):
        item = _ITEM.match(line)
        if item is None:
            continue
        note = item.group(1).strip()
        for word, instead in NOTE_SPEECH_BANNED.items():
            if _SPEECH_BANNED_RE[word].search(note):
                violations.append(
                    Violation(
                        "N24",
                        f"변경 항목의 `{word}`는 노트에 쓰지 않는다: {note[:50]}. "
                        f"`{instead}`로 적어라 - 모드가 내는 것은 음성 출력이고 "
                        "`말한다`는 모드를 사람처럼 만든다. 무엇을 발화하는지 "
                        "인용하는 `~라고 말함`만 살아 있다",
                    )
                )

    # N25 - 목록을 가르는 표지가 규칙 밖으로 느는 것.
    if changes in body_of:
        problem = _section_mark_problem(body_of[changes])
        if problem:
            violations.append(Violation("N25", problem))

    # N26 - 미검증 절이 원문에 없는 어구를 지어내는 것.
    for line in body_of.get(UNVERIFIED_SECTION, []):
        item = _ITEM.match(line)
        if item is None:
            continue
        note = item.group(1).strip()
        if _INVENTED_RE.search(note):
            violations.append(
                Violation(
                    "N26",
                    f"미검증 절의 줄이 `밝히-`를 쓴다: {note[:50]}. "
                    "절 제목이 주체와 조건을 이미 말하므로 줄마다 되풀이하지 않는다 - "
                    "원문에 없는 어구를 지어내는 자리이기도 하다. 종결은 "
                    f"`{UNVERIFIED_ENDINGS[0]}`이고, 개발자가 의견을 구하는 항목만 "
                    f"`{UNVERIFIED_ENDINGS[1]}`이다",
                )
            )

    # N9 - 인라인 링크.
    links = _LINK.findall(text)
    if links:
        violations.append(Violation("N9", f"인라인 링크를 쓰지 않는다: {', '.join(links)}"))

    # N10 - 전면 강조. 항목을 통째로 굵게 하면 강조가 아니라 배경이 된다.
    for line in lines:
        item = _ITEM.match(line)
        if item is None:
            continue
        rest = item.group(1)
        if rest and _emphasis_len(rest) * FULL_EMPHASIS_RATIO >= len(rest):
            violations.append(Violation("N10", f"항목을 통째로 강조했다: {line.strip()}"))

    # N11 - 강조 개수.
    for name, body in parts:
        bold = sum(len(_BOLD.findall(line)) for line in body)
        if bold > BOLD_PER_SECTION:
            violations.append(
                Violation(
                    "N11",
                    f"`{name or '서두'}` 절에 굵게가 {bold}개다. 절당 {BOLD_PER_SECTION}개까지다",
                )
            )
    italic = _ITALIC.findall(_BOLD.sub(" ", text))
    if italic:
        violations.append(Violation("N11", f"기울임을 쓰지 않는다: {', '.join(italic)}"))

    # N20 - 릴리스에서 걷어낸 자산. **백틱 안의 단독 이름만 본다** - 주소
    # 안의 경로(`.../docs/korean/README.ko.md`)는 파일을 받으라는 것이 아니라
    # 문서를 열라는 것이라 걸리면 안 된다.
    for quoted in re.findall(r"`([^`]*)`", text):
        dropped = DROPPED_ASSETS.get(quoted.strip())
        if dropped is not None:
            violations.append(
                Violation("N20", f"릴리스에 없는 자산을 가리킨다: `{quoted}`. {dropped}")
            )

    # N12 - 백틱 안 한글. 사용자가 손에 쥐는 파일 이름만 그 자리에 온다.
    for quoted in re.findall(r"`([^`]*)`", text):
        if _HANGUL.search(quoted) and quoted not in BACKTICK_HANGUL_OK:
            violations.append(
                Violation(
                    "N12",
                    f"백틱 안에 한글이 있다: `{quoted}`. "
                    + (
                        f"그 자리에 오는 것은 {', '.join(BACKTICK_HANGUL_OK)}뿐이다"
                        if BACKTICK_HANGUL_OK
                        else "릴리스 자산 이름은 전부 ASCII다. 받는 사람이 "
                        "릴리스 페이지에서 찾을 이름을 그대로 적어라"
                    ),
                )
            )

    # N13 - 말투. 사람이 읽는 문서라 습니다체다(모드가 말하는 문장과 반대다).
    strays = [n for n, kind in ko_style.endings(text) if kind == "한다체"]
    if len(strays) >= ko_style.MIXED_LIMIT:
        violations.append(
            Violation(
                "N13",
                f"한다체가 {len(strays)}곳이다({', '.join(str(n) for n in strays[:6])}행). "
                "노트는 사람이 읽는 문서라 습니다체다",
            )
        )

    # N14 - 내부 이름. `※` 줄의 `Dalamud`만 예외다 - 플러그인 로더 자체를 가리킨다.
    for number, line in enumerate(bare.splitlines(), 1):
        allowed = ("Dalamud",) if line.lstrip().startswith(NOTE_MARK) else ()
        banned = [w for w in commit_lint.NOTE_BANNED if w in line and w not in allowed]
        if banned:
            violations.append(
                Violation(
                    "N14",
                    f"{number}행에 내부 이름이 있다: {', '.join(banned)}. "
                    "사용자 화면에 뜨는 이름으로 바꿔라 - 직접 실행하는 파일 이름이면 "
                    "백틱으로 감싼다",
                )
            )

    # N18 - 소리로 갈리거나 모드가 안 쓰는 한국어 낱말. 목록이 규칙의 전부다.
    for number, line in enumerate(bare.splitlines(), 1):
        for word, instead in NOTE_KO_BANNED.items():
            if _KO_BANNED_RE[word].search(line):
                violations.append(
                    Violation("N18", f"{number}행의 `{word}`는 노트에 쓰지 않는다. {instead}")
                )

    # N15 - 자산 안내. 사람이 받을 것 하나를 위로 올리고 나머지를 여기서 내린다.
    marks = [line for line in lines if line.strip().startswith(NOTE_MARK)]
    tail = next((line for line in reversed(lines) if line.strip()), "")
    if len(marks) != 1 or tail.strip() != marks[0].strip():
        violations.append(
            Violation(
                "N15",
                f"`{NOTE_MARK}`로 시작하는 줄이 맨 끝에 하나 있어야 한다(지금 {len(marks)}개). "
                "나머지 자산이 무엇인지 알리는 자리다",
            )
        )

    # N16 - 도입 문단. 목록 절은 제목 바로 아래가 목록이다.
    #
    # **변경사항 절에만 예외 한 줄이 있다.** 모드만 바뀐 판은 위에 둘 항목이
    # 없어서 `모드 변경사항:`이 절의 첫 줄이 된다. 그 줄은 도입 문단이 아니라
    # 받는 방법을 가르는 신호이고, N8이 따로 본다. **연 것은 그 줄 하나지
    # 산문이 아니다** - 산문까지 열면 이 규칙이 그 절에서만 죽는다.
    for name in (n.format(version=version) for n in LIST_SECTIONS):
        listed_body = body_of.get(name)
        if listed_body is None:
            continue
        first = next((line for line in listed_body if line.strip()), "")
        if name == changes and first.startswith((MOD_PREFIX, KO_PREFIX)):
            continue
        if not _ITEM.match(first):
            violations.append(
                Violation(
                    "N16",
                    f"`{name}` 절이 목록으로 시작하지 않는다: {first.strip()}. "
                    "제목 바로 아래에 도입 문단을 두지 않는다",
                )
            )

    # N17 - 항목 둘이 한 줄로 붙은 것. **N16이 이걸 못 잡는다** - 그쪽은 절의
    # 첫 줄이 `- `로 시작하는지만 보고, 그 뒤에 표지가 또 나오는지는 안 본다.
    #
    # 2026-08-24에 실제로 그렇게 나갔다. 지난 판 넷에 미검증 줄을 소급해 넣는
    # 스크립트가 절 제목 뒤 줄바꿈을 먹어서 새 항목과 원래 첫 항목이 한 줄이
    # 됐고, 검사기가 초록이었다. 소리로 들으면 두 항목이 한 문장으로 이어진다.
    for line in text.splitlines():
        if not _ITEM.match(line):
            continue
        if _GLUED_ITEM.search(line):
            violations.append(
                Violation(
                    "N17",
                    f"항목 둘이 한 줄로 붙었다: {line.strip()[:60]}. "
                    "표지 앞에 줄바꿈을 넣어 항목을 나눠라",
                )
            )

    return violations


# --------------------------------------- 원본 노트 대비 커버리지 (N21·N22)
#
# **`v5.92`가 원본 절 넷 중 `## Werkzeug`를 통째로 빠뜨린 채 나갔고 검사기는
# 초록이었다.** 우리 노트 안만 보고 원본을 안 봤기 때문이다. 여기가 그 자리다.
#
# 기계가 못 하는 것을 먼저 적는다. **어느 우리 항목이 어느 원본 절에 대응하는지는
# 판정 불가다** - 독일어와 한국어라 글자가 안 겹치고, 원본 한 절이 우리 항목 셋이
# 되기도 한다. 그래서 세는 것은 **정보 단위의 개수**이고, 무엇을 빠뜨렸는지는
# 원본 절 이름을 그대로 돌려줘 사람이 대조한다.

#: 원본 절 제목. `##`과 `###`을 같이 센다 - `v5.93`은 큰 절 하나 아래 `###` 셋으로
#: 나뉘어 있었고, `##`만 세면 그 판의 정보 단위가 1이 된다.
_UP_HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$")

#: 원본이 든 실제 발화 예시. 인용 블록과 독일어 따옴표 둘 다 잡는다.
#: **`v5.93`이 이걸 통째로 빠뜨렸다** - 원본이 `> Gegner, jetzt 3 von 21. ...`로
#: 무엇이 어떻게 들리는지 보여 줬는데 우리 노트에는 그 자리가 없었다.
#:
#: **닫는 부호에 `“`(U+201C)가 빠져 있었다.** 독일어 표준 인용은 `„…“`이고
#: 업스트림은 독일어로 개발되는데, 정규식이 닫는 자리에 U+201D와 ASCII만 받아서
#: **정식으로 쓴 예시를 통째로 못 봤다.** 이 검사가 있는 이유가 `v5.93`이 발화
#: 예시를 잃은 것인데, 그 예시를 원본이 표준 부호로 쓰면 검사가 조용히 0건을
#: 돌려준다.
_UP_BLOCKQUOTE = re.compile(r"^>\s*(.+?)\s*$", re.M)
_UP_GERMAN_QUOTE = re.compile(r"„([^„“”\"]{4,}?)[\"“”]")

#: 꼬리 문단을 가르는 줄. 아래는 이번 판의 변경이 아니라 전체 이력 안내다.
_UP_TAIL = "\n---\n"

#: 원본 목록 항목.
_UP_ITEM = re.compile(r"^-\s+\S")


def upstream_units(text: str) -> dict:
    """원본 노트가 낸 정보 단위. 절 제목, 목록 항목 수, 발화 예시."""
    body = text.split(_UP_TAIL, 1)[0]
    sections = [m.group(2) for m in (_UP_HEADING.match(x) for x in body.splitlines()) if m]
    items = sum(1 for line in body.splitlines() if _UP_ITEM.match(line))
    quotes = _UP_BLOCKQUOTE.findall(body) + _UP_GERMAN_QUOTE.findall(body)
    return {"sections": sections, "items": items, "quotes": quotes}


def our_items(text: str, version: str) -> list[str]:
    """우리 노트의 변경 항목. `모드 변경사항:` 줄 아래와 위를 다 센다."""
    version = release_manifest.normalize_version(version)
    changes = CHANGES_SECTION.format(version=version)
    body = dict(split_sections(text)[1:]).get(changes, [])
    found = []
    for line in body:
        if line.startswith((MOD_PREFIX, KO_PREFIX)):
            continue
        item = _ITEM.match(line)
        if item is not None:
            found.append(item.group(1).strip())
    return found


#: 대조했다고 사람이 선언해야 넘어가는 코드. **N21은 여기 없다** - 개수 미달은
#: 선언으로 못 넘긴다.
ASK_CODES = ("N22", "N23")


def coverage(text: str, upstream: str, version: str) -> list[Violation]:
    """원본이 낸 것을 우리가 다 옮겼나.

    **개수만으로는 절 누락을 못 잡는다.** `v5.92`는 원본 정보 단위가 10인데
    우리 항목이 14개였다. `## Werkzeug`를 통째로 빼도 13이라 개수 검사를
    통과한다. 그래서 개수(N21)와 되묻기(N23·N22)를 갈랐다.

    - **N21**은 개수 미달이다. 위반이고 선언으로 못 넘긴다
    - **N23**은 원본 절 목록이다. 판마다 뜨고 사람이 대조한 뒤 넘긴다
    - **N22**는 원본이 든 실제 발화다. 있을 때만 뜨고 같은 방식으로 넘긴다

    **N21이 세는 것은 절 수다. 항목까지 더하지 않는다.** 우리 편집 기준은
    절충이라 - 잘못 알게 되는 것만 채우고 원본의 기술적 원인과 설계 이유는
    뺀다 - 원본 항목을 다 옮기지 않는 것이 정상이다. 항목까지 세면 제대로 쓴
    판도 걸려서, 그 자리가 곧 무시된다. 절 누락은 N23이 사람에게 목록으로
    되묻는 쪽이 맡는다.
    """
    units = upstream_units(upstream)
    want = len(units["sections"])
    got = len(our_items(text, version))

    violations: list[Violation] = []

    # **절이 하나도 없는 원본 노트는 받다가 깨진 것이다.** 그대로 두면 want가 0이라
    # 모든 검사가 조용히 통과한다 - `gh`가 실패해도 리다이렉트가 빈 파일을 남기므로
    # 이 모양이 실제로 나온다.
    if not units["sections"]:
        violations.append(
            Violation(
                "N21",
                "원본 노트에서 절을 하나도 못 찾았다. 받다가 깨졌거나 빈 파일이다 - "
                "이대로 두면 커버리지 검사가 통째로 조용해진다",
            )
        )
        return violations

    if got < want:
        violations.append(
            Violation(
                "N21",
                f"원본이 낸 절이 {want}개인데 우리 변경 항목은 {got}개다. "
                "절 하나가 우리 항목 여럿이 되는 것은 정상이고 그 반대가 사고다 - "
                "절보다 적게 적었으면 어느 절이 통째로 빠진 것이다",
            )
        )

    if units["sections"]:
        listed = "\n      ".join(f"- {name}" for name in units["sections"])
        violations.append(
            Violation(
                "N23",
                f"원본이 낸 절이 {len(units['sections'])}개다. "
                "각 절이 우리 노트 어디에 있는지 짚어라.\n"
                f"      {listed}\n"
                "      `v5.92`가 이 목록의 `Werkzeug`를 통째로 빠뜨린 채 나갔다. "
                "다 짚었으면 `--upstream-acked`로 다시 돌려라",
            )
        )

    if units["quotes"]:
        listed = "\n      ".join(f"- {q}" for q in units["quotes"])
        violations.append(
            Violation(
                "N22",
                "원본이 무엇이 어떻게 들리는지 실제 발화로 보여 준 자리가 "
                f"{len(units['quotes'])}곳이다.\n"
                f"      {listed}\n"
                "      우리 노트가 그 자리를 설명으로 뭉갰는지 확인해라 - 듣는 사람은 "
                "예시 한 줄로 아는 것을 설명 세 줄로는 모른다",
            )
        )
    return violations


def _print_rules() -> int:
    """명세 문서가 정한 규칙 목록. **여기서 지어내지 않고 문서를 읽어 낸다.**"""
    listed = rules()
    if not listed:
        print(f"규칙 표를 못 읽었다: {RULES_DOC}", file=sys.stderr)
        return 1

    print(f"릴리스 노트 검사 규칙 {len(listed)}개 - 명세는 {RULES_DOC.name}이 갖는다\n")
    for code, what in listed:
        print(f"  {code}: {what}")

    gaps = rule_gaps()
    if gaps:
        print("\n명세와 검사기가 갈렸다:", file=sys.stderr)
        for gap in gaps:
            print(f"  - {gap}", file=sys.stderr)
        return 1

    print(f"\n  검사기가 내는 번호와 문서의 번호가 같다({len(listed)}개).")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="릴리스 노트 본문을 검사한다")
    parser.add_argument("path", nargs="?", type=Path, help="검사할 노트. 안 주면 이번 판의 노트")
    parser.add_argument(
        "--rules",
        action="store_true",
        help="기계가 재는 규칙 목록을 낸다. 명세는 docs/dev/release-notes-rules.md가 갖는다",
    )
    parser.add_argument(
        "--version", help="이번 판 번호 (예: 5.95.0.0). 안 주면 파일 이름에서 뽑는다"
    )
    parser.add_argument(
        "--current-only",
        nargs="*",
        type=Path,
        metavar="노트",
        help=(
            "준 파일 중 이번 판의 노트 하나만 검사한다. 판 번호는 파일 이름에서 뽑는다. "
            "커밋 훅이 쓸 자리다 - 나가 있는 판은 소급해 고치지 않으므로 옛 판을 "
            "고치는 커밋이 여기서 막히면 안 된다. **이 저장소에는 그 훅이 아직 없다**"
        ),
    )
    parser.add_argument(
        "--upstream-notes",
        type=Path,
        help="원본 릴리스 노트 본문 파일. 주면 커버리지 규칙이 돈다",
    )
    parser.add_argument(
        "--upstream-acked",
        action="store_true",
        help="원본 절과 발화 목록을 사람이 대조했다. 되묻기(N22·N23)를 넘긴다",
    )
    parser.add_argument(
        "--upstream-unchanged",
        action="store_true",
        help="핀이 안 움직인 개정판이다. 옮길 원본 절이 없으므로 커버리지를 통째로 건너뛴다",
    )
    args = parser.parse_args(argv)

    if args.rules:
        return _print_rules()

    if args.current_only is not None:
        if args.version:
            parser.error("`--current-only`와 `--version`은 같이 못 쓴다")
        current = current_version()
        picked = [path for path in args.current_only if path.stem == current]
        if not picked:
            # 검사할 것이 없는 것은 정상이다. 옛 판만 고치는 커밋이 그렇다.
            print(f"건너뜀 - 이번 판({current})의 노트가 준 파일에 없다")
            return 0
        args.path = picked[0]
        args.version = current

    elif args.path is None:
        # **노트가 없는 것을 조용히 통과시키지 않는다.** 아직 안 쓴 것과 다 쓴
        # 것이 화면에서 같아지면, 첫 판을 노트 없이 낼 수 있다. `pack_check`와
        # `release_manifest`가 배포 폴더가 없을 때 하는 것과 같은 결이다.
        current = current_version()
        if current is None:
            print(
                f"검사할 노트가 없다: {NOTES_DIR}에 판 번호 이름의 노트 파일이 하나도 없다. "
                "첫 판 노트는 아직 안 썼다 - 쓰는 규약은 docs/release-notes/README.md가 갖고, "
                "본은 tools/notes-check/template.md다",
                file=sys.stderr,
            )
            return 1
        args.path = NOTES_DIR / f"{current}.md"
        args.version = args.version or current

    if not args.version:
        # 파일 하나가 판 하나이고 이름이 판 번호다. 이름에서 뽑으면 판 번호가
        # 파일과 어긋날 자리가 아예 없어진다.
        if not _VERSION_NAME.match(args.path.stem):
            parser.error(
                f"판 번호를 못 뽑는다: {args.path.name}. 이름이 `5.95.0.0.md` 꼴이 아니면 "
                "`--version`을 줘라"
            )
        args.version = args.path.stem

    if not args.path.is_file():
        print(f"릴리스 노트가 없다: {args.path}", file=sys.stderr)
        return 1

    text, violations = decode(args.path.read_bytes())
    if text:
        violations += check(text, args.version)

    # **건너뛴 것을 말한다.** 조용히 넘기면 원본을 안 본 판과 다 옮긴 판이
    # 화면에서 같아진다.
    skipped = ""
    acked: list[Violation] = []
    if args.upstream_unchanged:
        # **개정판은 옮길 절이 없다.** 네 번째 마디만 오르는 판은 원본이 그대로라,
        # 첫 판과 같은 잣대로 재면 같은 절을 판마다 다시 옮기라고 요구한다. `N21`은
        # 선언으로 못 넘기는 위반이라 그 요구가 곧 발행 중단이 된다 - `v5.93.0.1`이
        # 실제로 거기서 막혔고, 원본 v5.93의 절 넷은 `v5.93.0.0`이 이미 다 옮긴
        # 뒤였다. **면제는 부르는 쪽이 판단한다** - 검사기가 버전만 보고 알아서
        # 봐주면 핀을 옮기고도 안 옮긴 척하는 판을 못 가른다.
        skipped = (
            "핀이 안 움직인 개정판이라 커버리지(N21·N22·N23)를 안 봤다. "
            "옮길 원본 절은 앞 판이 이미 다 옮겼다"
        )
    elif args.upstream_notes is None:
        skipped = (
            "원본 노트를 안 줘서 커버리지(N21·N22·N23)를 안 봤다. "
            "`--upstream-notes <파일>`로 넘겨라"
        )
    elif not args.upstream_notes.is_file():
        print(f"원본 릴리스 노트가 없다: {args.upstream_notes}", file=sys.stderr)
        return 1
    elif text:
        found = coverage(text, args.upstream_notes.read_text(encoding="utf-8"), args.version)
        # 되묻기는 선언으로 넘긴다. 개수 미달(N21)은 못 넘긴다.
        for violation in found:
            if args.upstream_acked and violation.code in ASK_CODES:
                acked.append(violation)
            else:
                violations.append(violation)

    if violations:
        print(
            f"릴리스 노트가 규칙에 안 맞는다 (docs/dev/release-notes-rules.md): {args.path}",
            file=sys.stderr,
        )
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        return 1

    print(f"통과 - 절 {len(SECTION_NAMES)}개 구성과 마크업 규칙을 지켰다: {args.path}")
    print("  이 검사는 절 구성과 마크업과 `모드 변경사항:` 줄의 꼴만 본다.")
    print("  문장이 사실인가, 항목 순서가 맞나는 사람이 본다 - ko-release-notes 스킬")
    if acked:
        print(
            f"  [대조 선언] 되묻기 {len(acked)}건을 사람이 대조했다고 넘겼다: "
            f"{', '.join(v.code for v in acked)}"
        )
    if skipped:
        print(f"  [건너뜀] {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
