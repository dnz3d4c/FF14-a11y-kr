"""한국어 문장에 옮기다 만 영어가 남는 것을 잡는다.

막는 사고는 하나다 - **한국어 자리에 영어 낱말이 그대로 남는 것.** 모드가
말하는 문장이라 소리로 나가고, 읽는 사람은 옮겨졌다고 믿는다.

검사의 성패는 전처리가 가른다. `{name}`·`{count}` 같은 **보간 자리를 먼저
지워야** 한다 - 안 지우면 슬롯 이름까지 세서 수가 몇 배로 뛴다. 남는 것은
실측으로 전부 정당한 것이라, 통과 방법은 골든 허용목록이다. "명령어처럼 생긴
것"을 정규식으로 맞히려 들면 `of` 같은 진짜도 통과한다.
"""

import json

import pytest

import ko_words

GOLDEN = ko_words.LATIN_GOLDEN
CATALOG = ko_words.CATALOG


def 카탈로그(tmp_path, *korean: str):
    """`ko` 값만 갈아 끼운 임시 대장."""
    path = tmp_path / "strings.json"
    path.write_text(
        json.dumps({"strings": [{"ko": text} for text in korean]}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


# --- 전처리 - 보간 자리를 먼저 지운다 --------------------------------------


def test_보간_자리의_이름은_안_센다():
    # 이 한 줄이 수를 몇 배로 가른다.
    assert ko_words.latin_tokens("{name}, {count}개 남음.") == set()


def test_보간_자리_안의_코드도_안_센다():
    # 슬롯에는 C# 식이 통째로 들어 있다 - `int`·`MathF`가 새는 자리다.
    assert ko_words.latin_tokens("소리 {(int)MathF.Round(volume * 100)}퍼센트.") == set()


def test_자리_안에_또_자리가_있어도_안_센다():
    """정규식 하나로는 못 읽는 모양이다. **이 대장에 실제로 열 줄 있다.**

    `\\{[^{}]*\\}`는 안쪽 `{location}`만 잡고 그것을 감싼 바깥 자리를 통째로
    놓친다. 그러면 `location`·`null`·`string.Empty`가 "옮기다 만 영어"로
    허용목록에 쌓인다. 중괄호 깊이를 세는 `tools/assemble`의 것을 쓴다.
    """
    값 = '{name}{(location != null ? $", {location}에 있음" : "")}, {count} 중 {index}'
    assert ko_words.latin_tokens(값) == set()


def test_보간_자리_밖의_영어는_센다():
    assert ko_words.latin_tokens("{name}, HP {cur} 남음.") == {"HP"}


def test_두_번_겹친_중괄호는_보간_자리가_아니다():
    # C#에서 `{{`는 중괄호 한 개를 그대로 찍으라는 뜻이라, 안쪽은 사용자가 듣는
    # 글자다. 그래서 자리로 안 치고 센다.
    assert ko_words.latin_tokens("{{name}} 확인.") == {"name"}


def test_한국어와_숫자는_안_센다():
    assert ko_words.latin_tokens("남은 거리 30미터.") == set()


# --- 대장에서 모은다 -------------------------------------------------------


def test_옮기다_만_영어가_걸린다(tmp_path):
    words = ko_words.latin_words(카탈로그(tmp_path, "잠시 기다려라. Please wait."))
    assert words == {"Please", "wait"}


def test_한국어만_있으면_0건이다(tmp_path):
    assert ko_words.latin_words(카탈로그(tmp_path, "길안내를 켰다.")) == set()


# --- 골든 -----------------------------------------------------------------


def test_골든이_있다():
    assert GOLDEN.is_file(), f"{GOLDEN}가 없다 - ko_words.py --write로 만든다"


def test_골든이_정렬돼_있고_중복이_없다():
    words = json.loads(GOLDEN.read_text(encoding="utf-8"))["words"]
    assert words == sorted(set(words)), "정렬·중복 제거해서 저장한다 - diff가 읽히게"


def test_새_영어가_말없이_들어오지_않는다():
    # 빨개지면 둘 중 하나다. 옮기다 말았거나(고친다), 그대로 둬야 하는 낱말이
    # 새로 생겼거나(--write로 갱신하고 커밋 본문에 왜인지 적는다).
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["words"]
    now = sorted(ko_words.latin_words())

    added = [word for word in now if word not in golden]
    dropped = [word for word in golden if word not in now]
    assert not added, f"한국어 문장에 영어가 새로 들어왔다: {added}"
    assert not dropped, f"골든에만 남은 낱말이 있다 - --write로 갱신해라: {dropped}"


def test_허용목록은_사람이_훑을_수_있는_크기다():
    # 스물몇 개는 한 번에 읽힌다. 이 숫자가 크게 불면 허용목록이라는 방식 자체를
    # 다시 봐야 한다는 신호다 - 조용히 늘리라는 뜻이 아니다.
    words = json.loads(GOLDEN.read_text(encoding="utf-8"))["words"]
    assert len(words) < 60, f"허용목록이 {len(words)}개다 - 사람이 못 훑는다"


@pytest.mark.skipif(not CATALOG.is_file(), reason="대장이 없다")
def test_대장_전체를_읽는다():
    # 실물에서 한 줄도 안 읽고 0건을 내는 실패 모드를 막는다.
    assert ko_words.latin_words()
