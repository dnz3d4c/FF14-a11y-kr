"""사용자가 판정한 낱말이 되살아나는 것을 잡는다.

막는 사고는 하나다 - **판정 목록이 흩어지면 갈라지고, 갈라진 것을 아무도 못 본다.**
옛 저장소에서 2026-08-24 전수 검수가 낱말 74곳을 판정했는데 그 판정이 동결 문서에만
남았고, `고른 다음 건네주기`가 그대로 살아 있었다.

함정이 셋이라 갈라 시험한다. 대상을 안 가르면 노트의 낱말이 발화를 빨갛게
만들고, 경계를 안 두면 부분 문자열이 멀쩡한 줄을 잡고, `mod`에서 값 줄만
안 보면 독일어 원문이 검사 대상이 된다.
"""

import json

import pytest

import ko_lexicon


def _write(tmp_path, entries, rejected=()):
    """시험용 목록 파일. 실물 `lexicon.json`과 같은 꼴이다."""
    path = tmp_path / "lexicon.json"
    path.write_text(
        json.dumps({"entries": entries, "rejected": list(rejected)}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _entry(bad, good="대체어", why="근거", when="2026-08-31"):
    return {"bad": bad, "good": good, "why": why, "when": when}


def _empty():
    return {name: [] for name in ko_lexicon.TARGETS}


# ------------------------------------------------------------ 목록 위생


def test_why가_비면_거부한다(tmp_path):
    entries = _empty()
    entries["mod"] = [_entry("고른", why="")]
    problems = ko_lexicon.check_entries(_write(tmp_path, entries))
    assert any("why가 없다" in p for p in problems)


def test_when이_비면_거부한다(tmp_path):
    entries = _empty()
    entries["mod"] = [_entry("고른", when="")]
    problems = ko_lexicon.check_entries(_write(tmp_path, entries))
    assert any("when이 없다" in p for p in problems)


def test_같은_낱말이_두_번이면_거부한다(tmp_path):
    entries = _empty()
    entries["mod"] = [_entry("고른"), _entry("고른")]
    problems = ko_lexicon.check_entries(_write(tmp_path, entries))
    assert any("두 번 있다" in p for p in problems)


def test_대상이_빠지면_거부한다(tmp_path):
    entries = {"mod": []}
    problems = ko_lexicon.check_entries(_write(tmp_path, entries))
    assert any("대상이 없다" in p for p in problems)


def test_기각한_낱말이_목록에도_있으면_거부한다(tmp_path):
    # 둘 중 하나가 거짓말이다. 넣기로 정했으면 rejected에서 빼야 한다.
    entries = _empty()
    entries["mod"] = [_entry("끝")]
    rejected = [{"bad": "끝", "target": "mod", "why": "오탐 일곱", "when": "2026-08-31"}]
    problems = ko_lexicon.check_entries(_write(tmp_path, entries, rejected))
    assert any("둘 다 있다" in p for p in problems)


def test_실물_목록이_규약을_지킨다():
    assert ko_lexicon.check_entries() == []


@pytest.mark.parametrize("target", ko_lexicon.TARGETS)
def test_실물_목록의_대상이_비어_있지_않다(target):
    assert ko_lexicon.entries(target)


def test_사람이_읽는_판정은_안_읽는다():
    # `plain_words`와 `actions`는 스킬이 갖는 판정이라 기계가 안 잰다.
    # 여기서 읽으면 `check_entries`가 그 둘의 꼴까지 요구하게 된다.
    data = ko_lexicon.load()
    assert "plain_words" in data and "actions" in data
    assert set(data["entries"]) == set(ko_lexicon.TARGETS)


# ------------------------------------------------------------ 대상 격리


def test_노트의_낱말이_발화에_안_걸린다(tmp_path):
    # 같은 낱말이라도 자리에 따라 판정이 다르다. 대상을 안 가르면 목록 하나가
    # 세 대상을 전부 빨갛게 만든다.
    entries = _empty()
    entries["note"] = [_entry("거절", "취소")]
    path = _write(tmp_path, entries)
    lines = ['      "ko": "거절함."']
    assert ko_lexicon.scan(lines, "mod", "x", path) == []
    assert ko_lexicon.scan(["거절함"], "note", "x", path)


def test_모르는_대상은_거부한다():
    with pytest.raises(ValueError):
        ko_lexicon.entries("무엇")


# ------------------------------------------------------------ 낱말 경계


def test_앞에_한글이_붙으면_안_잡는다(tmp_path):
    # 처음 판이 부분 문자열로 재서 이미 나간 판 둘을 빨갛게 만들었다.
    entries = _empty()
    entries["note"] = [_entry("다리", "위쪽이 막힌 곳")]
    path = _write(tmp_path, entries)
    assert ko_lexicon.scan(["기다리는지 봄"], "note", "x", path) == []
    assert ko_lexicon.scan(["다리 위에서"], "note", "x", path)


def test_뒤에_조사가_붙어도_잡는다(tmp_path):
    entries = _empty()
    entries["note"] = [_entry("다리", "위쪽이 막힌 곳")]
    path = _write(tmp_path, entries)
    assert ko_lexicon.scan(["다리를 지나감"], "note", "x", path)


def test_인라인_코드는_안_본다(tmp_path):
    # 백틱 안은 실물 문구를 인용하는 자리다. `ko_style`·`notes_check`와 같다.
    entries = _empty()
    entries["doc"] = [_entry("기능 전체", "모드 기능")]
    path = _write(tmp_path, entries)
    assert ko_lexicon.scan(["`기능 전체`라고 말합니다"], "doc", "x", path) == []
    assert ko_lexicon.scan(["기능 전체를 켭니다"], "doc", "x", path)


# ------------------------------------------------------------ 발화 값 줄


def test_발화는_ko_값_줄만_본다(tmp_path):
    # 독일어 원문과 영어 원문은 우리 판정 대상이 아니다.
    entries = _empty()
    entries["mod"] = [_entry("고른", "선택한")]
    path = _write(tmp_path, entries)
    lines = [
        '      "de": "고른",',
        '      "en": "고른",',
        '      "ko": "고른 다음 건네주기."',
    ]
    found = ko_lexicon.scan(lines, "mod", "x", path)
    assert len(found) == 1
    assert "x:3" in found[0]


def test_고친_결과가_통과한다(tmp_path):
    entries = _empty()
    entries["mod"] = [_entry("고른", "선택한")]
    path = _write(tmp_path, entries)
    assert ko_lexicon.scan(['      "ko": "선택한 다음 건네주기."'], "mod", "x", path) == []


# ------------------------------------------------------------ 정규식 항목


TELEGRAM = r"(?<![가이은는]) 필요\."


def _regex_entry(bad=TELEGRAM, good="`~해야 함.`"):
    return {**_entry(bad, good), "regex": True}


@pytest.mark.parametrize(
    ("ko", "caught"),
    [
        ("먼저 목적지 설정 필요.", True),
        ("설정이 필요.", False),
        ("추가 설정은 필요.", False),
        ("이 키는 필요.", False),
        # `도`는 조사로 안 본다. `시도`처럼 명사가 `도`로 끝나는 것과 글자로
        # 못 가르고, 교정 전 대장의 27건 중 6건이 `다시 시도 필요.`였다.
        # `설정도 필요.`가 걸리는 오탐을 그 대가로 받는다.
        ("잠시 뒤 다시 시도 필요.", True),
        ("추가 설정도 필요.", True),
    ],
)
def test_실물_전보문_항목의_경계(ko, caught):
    # 교차 리뷰 지적(2026-10-01): `가`·`이`만 인정하면 `은`·`는`이 붙은
    # 온전한 문장이 걸린다.
    line = f'      "ko": "{ko}"'
    assert bool(ko_lexicon.scan([line], "mod", "x")) is caught


def test_정규식_항목은_틀을_잡는다(tmp_path):
    # 리터럴로는 `<명사> 필요.`를 못 잡는다 - 앞 명사가 문장마다 다르다.
    entries = _empty()
    entries["mod"] = [_regex_entry()]
    path = _write(tmp_path, entries)
    found = ko_lexicon.scan(['      "ko": "먼저 목적지 설정 필요."'], "mod", "x", path)
    assert len(found) == 1


@pytest.mark.parametrize(
    "ko",
    [
        "먼저 목적지를 설정해야 함.",
        ", 다른 클래스가 필요",
        ", {required}마리 필요",
        "HQ 재료가 필요함: 간이 제작.",
    ],
)
def test_정규식_항목은_온전한_문장을_통과시킨다(tmp_path, ko):
    entries = _empty()
    entries["mod"] = [_regex_entry()]
    path = _write(tmp_path, entries)
    assert ko_lexicon.scan([f'      "ko": "{ko}"'], "mod", "x", path) == []


def test_정규식이_아닌_항목은_기호를_글자로_본다(tmp_path):
    # 표시가 없으면 지금처럼 리터럴이다. `.`이 아무 글자나 잡으면 안 된다.
    entries = _empty()
    entries["mod"] = [_entry("필요.")]
    path = _write(tmp_path, entries)
    assert ko_lexicon.scan(['      "ko": "필요함"'], "mod", "x", path) == []


def test_깨진_정규식은_목록_위생에서_거부한다(tmp_path):
    entries = _empty()
    entries["mod"] = [_regex_entry(bad="(필요")]
    problems = ko_lexicon.check_entries(_write(tmp_path, entries))
    assert any("정규식" in p for p in problems)


@pytest.mark.parametrize("target", ["note", "doc"])
def test_정규식_항목은_발화에만_둔다(tmp_path, target):
    # `note`·`doc`은 ko_style·notes_check가 따로 읽고 리터럴로 잰다. 거기 두면
    # 틀이 글자 그대로 찾아져 아무것도 안 잡고 조용히 통과한다.
    entries = _empty()
    entries[target] = [_regex_entry()]
    problems = ko_lexicon.check_entries(_write(tmp_path, entries))
    assert any("mod에만" in p for p in problems)


# ------------------------------------------------------------ 실물 검사


def test_발화_대장이_korean_아래에_있다():
    # 옛 저장소에서 `overlay/ko/ko.json`이던 자리다. 경로가 갈리면 이 검사가
    # 아무것도 안 훑고 조용히 통과한다.
    path = ko_lexicon.DEFAULT_PATHS["mod"][0]
    assert path.is_file(), path
    assert path.name == "strings.json"


def test_발화에_되살아난_낱말이_없다():
    path = ko_lexicon.DEFAULT_PATHS["mod"][0]
    assert ko_lexicon.scan_file(path, "mod") == []


def test_발행한_노트에_되살아난_낱말이_없다():
    # **발행본은 소급해 고치지 않는다.** 그래서 여기가 빨개지면 고칠 것은
    # 노트가 아니라 목록이다 - 그 낱말이 그 자리에서 정당했다는 뜻이다.
    paths = ko_lexicon.DEFAULT_PATHS["note"]
    if not paths:
        pytest.skip("발행한 노트가 아직 없다 - 첫 판 노트는 다음 단계에서 쓴다")
    for path in paths:
        assert ko_lexicon.scan_file(path, "note") == [], path.name


def test_노트_기본_경로가_없으면_명령이_소리를_낸다(capsys):
    # 조용히 0으로 끝나면 "검사할 것이 없다"와 "다 통과했다"가 같아진다.
    if ko_lexicon.DEFAULT_PATHS["note"]:
        pytest.skip("노트가 생겼다 - 이 갈래는 더 안 돈다")
    assert ko_lexicon.main(["--target", "note"]) == 1
    assert "기본 경로가 없다" in capsys.readouterr().err


def test_기각한_낱말은_넣으면_오탐이_난다(tmp_path):
    # `끝`을 뺀 근거를 실물로 붙잡아 둔다. 다음 사람이 "부류 D에 있는데 왜
    # 없지"라며 도로 넣으면 이 검사가 그 이유를 보여 준다.
    entries = _empty()
    entries["mod"] = [_entry("끝", "종료")]
    path = _write(tmp_path, entries)
    found = ko_lexicon.scan_file(ko_lexicon.DEFAULT_PATHS["mod"][0], "mod", path)
    assert len(found) >= 7
