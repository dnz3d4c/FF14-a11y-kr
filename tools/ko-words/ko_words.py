"""번역이 쓰는 낱말 중 게임에 없는 것을 골라내 고정한다.

## 무엇을 막나

**게임이 안 쓰는 낱말을 그럴듯해서 쓰는 것.** 대장(`korean/terms.json`)이
같은 사고를 막으라고 있지만, 대장은 "적어 둔 낱말"만 본다 - 적기를 잊으면
아무 일도 안 일어난다. 실제로 그렇게 됐다. 대장이 28줄일 때 번역은 그 두 배가
넘는 게임 낱말을 쓰고 있었고, 그중 여섯이 게임에 아예 없는 말이었다
(`장판`·`손패`·`방위`·`월드`·`훈련장`·`우편함`).

대장의 `not_found`가 그 판정을 담는다 - "이 낱말은 게임에 없으니 안 쓴다"고
적어 둔 자리다. 적어 두기만 해서는 아무것도 안 지켜진다. 이 검사가 그 판정이
번역으로 되돌아오는 것을 막는다.

그래서 반대 방향에서 본다. 번역이 실제로 쓰는 낱말을 전부 모아 게임 덤프에
없는 것을 골라내고, **그 목록 자체를 골든으로 고정한다.** 새 낱말이 말없이
들어오면 빨개진다.

## 0건이 곧 잘못은 아니다

모드가 지어야 하는 말이 있다 - `길안내`·`발자취`·`경유지` 같은 것은 게임에
없는 개념이라 게임 시트에 있을 리가 없다. 그래서 이 검사는 "0건 금지"가
아니라 **"0건 목록이 조용히 늘지 않는다"**이다. 새로 늘었으면 둘 중 하나고,
어느 쪽인지는 사람이 정한다.

- 게임 낱말을 잘못 지어냈다 → 고친다
- 모드가 지어야 하는 말이 새로 생겼다 → `--write`로 갱신하고 **커밋 본문에
  왜인지 적는다**. 조용히 갱신하면 이 장치는 그날로 죽는다

## 어디를 보나

`korean/strings.json`의 한국어와, **대장을 안 거치고 소스에 직접 박힌
한국어**다. 뒤엣것이 옛 저장소의 "손 케이스"에 해당한다 - 거기서는 업스트림
클론의 작업 브랜치에 쌓인 커밋을 제목으로 찾아 읽었는데, 이 저장소에는 그런
브랜치가 없다. 대신 `kr/`(원본에 없는 신규 파일)와 `replace/`(원본을 통째로
대체하는 사본)가 자기 문장을 한국어까지 넣어 갖고 있어서, 그 트리를 그대로
읽는다.

**보는 것은 `FF14Accessibility/` 아래뿐이다.** `Installer/`와 `Launcher/`는
자체 사전이 세 언어를 들고 있어 대장을 안 거치고(`tools/assemble/assemble.py`의
`SOURCE_NAME`), 그쪽 한국어는 `tools/loc-check`가 따로 본다.

## Addon 시트만 본다

`tools/ko-terms`는 시트 넷(`Addon`·`Action`·`Pet`·`Status`)을 뽑지만 여기서
읽는 것은 Addon 하나다. **묻는 것이 "게임이 이 낱말을 UI에서 쓰나"이기
때문이다.** 대장의 `not_found`가 그렇게 판정해 두었다 - `지형`은
`Action 18244행이 '지형 파괴 공격'이고 ... UI 낱말이 아닐 뿐이지 게임이 안 쓰는
말은 아니다`이고, `장판`도 `Action 시트에 '장판 뒤집기'가 7행 있다`면서 그대로
쓰기로 정했다.

넷을 다 읽으면 이 판정들이 통째로 조용해진다. 실측으로 Addon만 볼 때 259건,
넷을 다 볼 때 215건이고, 사라지는 44건에 `장판`·`지형`·`통로`가 들어 있다
(2026-09-04). 특히 `월드`는 넷에서 Action의 `헬로 월드`(기술 이름)로만 잡히는데,
그 한 줄 때문에 `DCSelected`를 안 옮기기로 한 근거가 사라진다.

## 두 번째 검사 - 옮기다 만 영어

같은 자리에서 반대쪽 구멍도 막는다. 위 검사는 `[가-힣]{2,}`만 세서 **한국어
문장에 영어가 그대로 남은 것**을 아예 안 봤다. 그래서 대장의 한국어에서
보간 자리를 지우고 라틴 문자를 세, 그 목록을 따로 골든으로 고정한다
(`golden/latin-words.json`).

**남는 것이 전부 잘못은 아니다.** 게임 표기(`HP`·`NPC`), 사용자가 그대로 쳐야
하는 명령어(`/acc help`), 고유명사(`Dalamud`·`vnavmesh`)는 영어로 있어야 맞다.
그래서 정규식으로 "명령어처럼 생긴 것"을 맞히지 않고 **허용목록**으로 둔다 -
그렇게 하면 `of` 같은 진짜도 같이 통과한다.

**이 검사는 대장만 본다.** 소스에 직접 박힌 영어(`FATEs`)는 여기 안 걸린다 -
대장을 거치지 않는 자리라 `tools/ko-speech`의 몫이다. 이것 하나로 다 막히지
않는다.

사용법:
    uv run python tools/ko-words/ko_words.py           # 대조
    uv run python tools/ko-words/ko_words.py --write   # 골든 갱신
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# 덤프의 이름과 시트 목록은 `tools/ko-terms`가 갖고 있다 - 같은 규약을 두 벌로
# 적으면 시트가 늘 때 한쪽만 따라오고, 못 따라온 쪽은 조용히 덜 읽는다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ko-terms"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assemble"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import terms as ko_terms  # noqa: E402 - 위에서 경로를 넣어야 찾는다

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다
import scanner  # noqa: E402 - 위에서 경로를 넣어야 찾는다

CATALOG = REPO / "korean" / "strings.json"
TERMS = REPO / "korean" / "terms.json"
GOLDEN = Path(__file__).resolve().parent / "golden" / "mod-words.json"
LATIN_GOLDEN = Path(__file__).resolve().parent / "golden" / "latin-words.json"

#: 게임 덤프. UI 문자열 시트 하나만 본다 - 까닭은 모듈 머리글에 있다. 이름을
#: 짓는 규약은 `tools/ko-terms`가 갖는다.
SHEET = ko_terms.DEFAULT_SHEET
DUMP = ko_terms.dump_path(SHEET)

#: 대장을 안 거치고 소스에 직접 박힌 한국어가 사는 곳. 조립이 얹는 두 트리이고,
#: 그중 모드 트리만 본다 - 설치 프로그램은 자체 사전을 쓴다.
HAND_ROOTS = (
    REPO / "kr" / "FF14Accessibility",
    REPO / "replace" / "FF14Accessibility",
)

#: 한 글자는 조사·의존명사라 신호가 없다.
TOKEN = re.compile(r"[가-힣]{2,}")

#: 한 글자짜리도 센다 - 키 이름 `F1`이 그 자리다.
LATIN = re.compile(r"[A-Za-z]+")

#: 낱말에 붙은 조사. **떼어 낸 나머지가 게임에 있을 때만** 떼어낸 것으로 친다 -
#: 그래서 `소지품에`는 `소지품`으로 잡히고 `장판`은 아무것도 못 떼어 그대로 남는다.
#: 긴 것부터 본다: `에게`를 `에`로 먼저 자르면 `누구에`가 남는다.
PARTICLES = (
    "에서는", "에게서", "으로는", "이라는", "이라고", "에게는", "까지는",
    "에서", "에게", "으로", "이라", "부터", "까지", "보다", "처럼", "마다",
    "한테", "밖에", "조차", "이나", "이란", "라는", "라고",
    "은", "는", "이", "가", "을", "를", "에", "와", "과", "의", "도", "만",
    "로", "나", "야", "아", "뿐", "께",
)  # fmt: skip


def tokens(text: str) -> set[str]:
    """한국어 낱말. 보간 자리·영문·숫자는 이 검사 대상이 아니다."""
    return set(TOKEN.findall(text))


def latin_tokens(text: str) -> set[str]:
    """사용자가 듣게 되는 영어 낱말. **보간 자리를 먼저 지운다.**

    자리 안에는 슬롯 이름만이 아니라 C# 식이 통째로 들어 있어서
    (`{(int)MathF.Round(volume * 100)}`) 지우지 않으면 라틴 문자 검사가 그것들을
    다 센다.

    자리를 정규식으로 잡으면 **중첩된 자리를 못 읽는다.** 이 대장에는
    `{(location != null ? $", {location}에 있음" : "")}`처럼 자리 안에 또 자리가
    든 값이 열 줄 있고, `\\{[^{}]*\\}`는 안쪽만 잡고 바깥을 통째로 놓친다. 그러면
    `location`·`null`·`string.Empty`가 "옮기다 만 영어"로 허용목록에 쌓인다.
    그래서 중괄호 깊이를 세는 `tools/assemble`의 것을 그대로 쓴다 - 조립이 값을
    자르는 걸음과 같아야 두 도구가 같은 글자를 본다. `{{`는 중괄호를 그대로
    찍으라는 C# 표기라 자리가 아니고, 안쪽이 사용자가 듣는 글자다.
    """
    return set(LATIN.findall(scanner.outside_holes(text)))


def latin_words(catalog: Path = CATALOG) -> set[str]:
    """대장의 한국어에 남은 영어.

    소스에 직접 박힌 자리는 안 본다 - 거기는 C# 식별자가 통째로 섞여 들어온다.
    소스에 박힌 영어는 이 검사의 몫이 아니다(모듈 머리글 참고).
    """
    rows = json.loads(catalog.read_text(encoding="utf-8"))["strings"]
    found: set[str] = set()
    for row in rows:
        found |= latin_tokens(row["ko"])
    return found


def load_dump(path: Path = DUMP) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def hand_lines(roots: tuple[Path, ...] = HAND_ROOTS) -> list[str]:
    """대장을 안 거치고 소스에 직접 박힌 줄.

    **주석은 먼저 지운다.** 주석은 사용자에게 안 나가는 글인데, 거기 적힌
    한국어가 섞이면 "번역이 쓰는 낱말"이 아닌 것이 골든에 쌓인다. 지우는 장치는
    `tools/assemble`의 것을 그대로 쓴다.

    한국어가 든 줄만 돌려준다. C# 전체를 넘겨도 `tokens`가 한글만 세지만,
    돌려주는 것이 무엇인지 이름과 맞아야 부르는 쪽이 오해하지 않는다.
    """
    found: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.cs")):
            stripped = scanner.strip_comments(path.read_text(encoding="utf-8"))
            found += [line for line in stripped.splitlines() if TOKEN.search(line)]
    return found


def korean_text(catalog: Path = CATALOG, roots: tuple[Path, ...] = HAND_ROOTS) -> list[str]:
    """번역이 실제로 내보내는 한국어. 대장과 소스에 박힌 자리 둘 다."""
    rows = json.loads(catalog.read_text(encoding="utf-8"))["strings"]
    return [row["ko"] for row in rows] + hand_lines(roots)


def known_terms(path: Path = TERMS) -> set[str]:
    """대장에 시트와 행 번호가 함께 적힌 낱말. 이미 확인된 것이라 다시 안 센다."""
    if not path.is_file():
        return set()
    rows = json.loads(path.read_text(encoding="utf-8"))["terms"]
    return {row["ko"] for row in rows}


def in_game(word: str, dump: str) -> bool:
    """게임이 이 낱말을 쓰나. 조사는 **떼어 낸 나머지가 게임에 있을 때만** 뗀다."""
    if word in dump:
        return True
    for particle in PARTICLES:
        stem = word.removesuffix(particle)
        if stem != word and len(stem) >= 2 and stem in dump:
            return True
    return False


def unknown(texts: list[str], dump: str, terms: set[str] | None = None) -> set[str]:
    """덤프에도 대장에도 없는 낱말.

    덤프는 통짜 문자열로 훑는다. 낱말이 어느 행에 있는지가 아니라 **게임이 그
    낱말을 쓰긴 하는가**가 질문이라, 부분 문자열 일치면 충분하다.
    """
    found: set[str] = set()
    for text in texts:
        found |= tokens(text)
    return {word for word in found if not in_game(word, dump)} - (terms or set())


def check_latin(write: bool) -> int:
    """한국어에 남은 영어를 허용목록과 대조한다."""
    now = sorted(latin_words())

    if write:
        LATIN_GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        LATIN_GOLDEN.write_text(
            json.dumps(
                {
                    "note": "한국어 문장에 그대로 남은 영어. 여기 있는 것은 "
                    "영어로 있어야 맞다고 사람이 확인한 것이다 - 게임 "
                    "표기(HP·NPC), 사용자가 그대로 쳐야 하는 명령어"
                    "(/acc help), 고유명사(Dalamud·vnavmesh), 키 이름"
                    "(F1). 늘어날 때 왜인지 커밋 본문에 적는다.",
                    "source": "korean/strings.json (보간 자리를 지운 뒤)",
                    "words": now,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"영어 골든 갱신: {len(now)}개")
        return 0

    if not LATIN_GOLDEN.is_file():
        print(f"영어 골든이 없다 - --write로 만든다: {LATIN_GOLDEN}", file=sys.stderr)
        return 1

    golden = json.loads(LATIN_GOLDEN.read_text(encoding="utf-8"))["words"]
    added = [word for word in now if word not in golden]
    dropped = [word for word in golden if word not in now]
    if added or dropped:
        print("영어 골든과 다르다:", file=sys.stderr)
        for word in added:
            print(f"  + {word}  (한국어 문장에 영어가 새로 들어왔다)", file=sys.stderr)
        for word in dropped:
            print(f"  - {word}  (이제 안 쓴다 - --write로 갱신해라)", file=sys.stderr)
        return 1

    print(f"통과 - 한국어에 남은 영어 {len(now)}개, 골든 그대로")
    return 0


def main(argv: list[str]) -> int:
    console.setup()
    write = "--write" in argv
    require_dump = "--require-dump" in argv

    # 영어 검사는 대장만 보면 되므로 게임 덤프가 없어도 돈다.
    rc = check_latin(write)

    if not DUMP.is_file():
        # **건너뛰기가 정상인 자리와 아닌 자리가 다르다.** 개발 머신에서는
        # 덤프를 sqpack에서 뽑아 두는 것이라 없을 수 있고 그때는 넘어가는 것이
        # 맞다. 릴리스 경로와 CI에서는 아니다 - 그쪽에서 조용히 건너뛰면
        # 낱말 검사가 한 번도 안 돈 채로 판이 나간다.
        if require_dump:
            print(
                f"[실패] 게임 데이터 덤프가 없다: {DUMP}\n"
                f"  --require-dump 로 불렀으므로 건너뛰지 않는다. "
                f"뽑는 법은 tools/ko-terms/README.md"
            )
            return 1
        print(f"게임 데이터 덤프가 없다 - 건너뛴다: {DUMP}")
        return rc

    now = sorted(unknown(korean_text(), load_dump(), known_terms()))

    if write:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(
            json.dumps(
                {
                    "note": "번역이 쓰는데 게임 UI 시트에는 없는 낱말. 대개는 "
                    "모드가 지어야 하는 말이다 - 게임에 없는 개념이라 "
                    "게임 시트에 있을 리가 없다. 늘어날 때 왜인지 "
                    "커밋 본문에 적는다.",
                    "source": "korean/strings.json + kr·replace의 FF14Accessibility 소스",
                    "sheet": SHEET,
                    "words": now,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"골든 갱신: {len(now)}개")
        return rc

    if not GOLDEN.is_file():
        print(f"골든이 없다 - --write로 만든다: {GOLDEN}", file=sys.stderr)
        return 1

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["words"]
    added = [word for word in now if word not in golden]
    dropped = [word for word in golden if word not in now]
    if added or dropped:
        print("골든과 다르다:", file=sys.stderr)
        for word in added:
            print(f"  + {word}  (게임에 없는 낱말이 새로 들어왔다)", file=sys.stderr)
        for word in dropped:
            print(f"  - {word}  (이제 안 쓴다 - --write로 갱신해라)", file=sys.stderr)
        return 1

    print(f"통과 - 게임에 없는 낱말 {len(now)}개, 골든 그대로")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
