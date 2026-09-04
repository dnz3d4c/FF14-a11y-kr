"""번역이 쓰는 낱말 중 게임에 없는 것의 목록을 고정한다.

막는 사고는 하나다 - **게임이 안 쓰는 낱말을 그럴듯해서 쓰는 것.** 검수에서
실제로 나왔다: `장판`(플레이어 은어), `손패`, `방위`, `월드`, `훈련장`,
`우편함`. 전부 KR Addon 시트에 0건인데 뜻이 통해서 안 걸렸다.

대장(`korean/terms.json`)은 "쓴 낱말"이 아니라 "적어 둔 낱말"만 본다. 적기를
잊으면 아무 일도 안 일어난다. 그래서 반대 방향에서 본다 - 번역이 쓰는 낱말을
전부 모아 게임 덤프에 없는 것을 골라내고, 그 목록을 골든으로 고정한다.
"""

import json

import pytest

import ko_words

GOLDEN = ko_words.GOLDEN
DUMP = ko_words.DUMP


# --- 구조 - 늘 돈다 --------------------------------------------------------


def test_골든이_있다():
    assert GOLDEN.is_file(), f"{GOLDEN}가 없다 - ko_words.py --write로 만든다"


def test_골든이_정렬돼_있고_중복이_없다():
    words = json.loads(GOLDEN.read_text(encoding="utf-8"))["words"]
    assert words == sorted(set(words)), "정렬·중복 제거해서 저장한다 - diff가 읽히게"


def test_낱말을_뽑는다():
    got = ko_words.tokens("길안내 켜짐. {count}개, ABC.")
    assert got == {"길안내", "켜짐"}, got


def test_한_글자와_숫자와_영문은_안_센다():
    # 한 글자는 조사·의존명사라 신호가 없고, 영문·숫자는 이 검사 대상이 아니다.
    assert ko_words.tokens("길 3개 HP") == set()


def test_게임에_있는_낱말은_안_걸린다():
    unknown = ko_words.unknown(["소지품에 아이템 없음."], "520\t소지품\n953\t아이템\n")
    assert unknown == {"없음"}


def test_게임에_없는_낱말이_걸린다():
    unknown = ko_words.unknown(["장판 경고 켜짐."], "520\t소지품\n")
    assert "장판" in unknown


# --- 어느 시트를 보나 ------------------------------------------------------


def test_UI_문자열_시트만_본다():
    """`tools/ko-terms`가 넷을 뽑아도 여기서 읽는 것은 Addon 하나다.

    묻는 것이 "게임이 이 낱말을 UI에서 쓰나"라서다. 대장의 `not_found`가 그렇게
    판정해 두었다 - `지형`은 `Action 18244행이 '지형 파괴 공격'`이지만 UI 낱말이
    아니라 안 쓰기로 했고, `월드`도 Action의 `헬로 월드`(기술 이름)뿐이라
    `DCSelected`를 안 옮기기로 했다. 넷을 다 읽으면 그 판정들이 통째로 조용해진다
    (실측으로 259건에서 215건으로 줄고, 사라지는 44건에 `장판`·`지형`이 있다).
    """
    assert ko_words.SHEET == "Addon"
    assert ko_words.DUMP.name == "addon-Korean.tsv"


def test_기술_이름만_있는_낱말은_UI에_없는_것으로_센다():
    # Action 시트의 `헬로 월드`가 Addon 덤프에는 없다. 그 한 줄 때문에 `월드`가
    # 통과하면 `DCSelected`를 안 옮긴 근거가 사라진다.
    assert "월드" in ko_words.unknown(["월드 선택됨."], "520\t소지품\n")


# --- 소스에 직접 박힌 한국어 -----------------------------------------------


def test_소스에_박힌_한국어를_읽는다(tmp_path):
    """대장을 안 거치고 `kr/`·`replace/`에 박힌 자리도 번역이 내보내는 말이다.

    옛 저장소에서는 작업 브랜치의 커밋을 제목으로 찾아 읽었고, 거기서 `월드`가
    나왔다. 이 저장소에는 그 브랜치가 없고 트리가 그대로 있다.
    """
    root = tmp_path / "FF14Accessibility"
    (root / "Compat").mkdir(parents=True)
    (root / "Compat" / "CompatReport.cs").write_text(
        'class T {\n    // 주석\n    string M() => Pick("de", "en", "호환성 안내");\n}\n',
        encoding="utf-8",
    )
    assert ko_words.hand_lines((root,)) == ['    string M() => Pick("de", "en", "호환성 안내");']


def test_한글이_없는_줄은_안_읽는다(tmp_path):
    root = tmp_path / "FF14Accessibility"
    root.mkdir(parents=True)
    (root / "Plain.cs").write_text("class T { void M() { } }\n", encoding="utf-8")
    assert ko_words.hand_lines((root,)) == []


def test_트리가_없어도_죽지_않는다(tmp_path):
    assert ko_words.hand_lines((tmp_path / "없다",)) == []


def test_실물_트리에서_읽는다():
    # 배선만 되고 0줄을 읽으면 살아 있는지 알 수 없다. `kr/`의 `CompatReport.cs`가
    # 자기 문장을 한국어까지 넣어 갖고 있다.
    assert ko_words.hand_lines(), "kr·replace에서 한 줄도 못 읽었다"


# --- 게임 데이터와 대조 - 덤프가 있을 때만 --------------------------------


@pytest.mark.skipif(
    not DUMP.is_file(),
    reason="게임 데이터 덤프가 없다 - tools/ko-terms/README.md",
)
def test_새_낱말이_말없이_들어오지_않는다():
    # 빨개지면 둘 중 하나다. 게임 낱말을 잘못 지어냈거나(고친다), 모드가 지어야
    # 하는 말이 새로 생겼거나(--write로 갱신하고 커밋 본문에 왜인지 적는다).
    # `known_terms`를 빼는 것까지가 도구가 골든에 적는 걸음이다. 안 빼면 이
    # 검사가 도구보다 엄해져서 `--write` 뒤에도 안 초록이 된다.
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["words"]
    now = sorted(
        ko_words.unknown(ko_words.korean_text(), ko_words.load_dump(), ko_words.known_terms())
    )

    added = [word for word in now if word not in golden]
    dropped = [word for word in golden if word not in now]
    assert not added, f"게임에 없는 낱말이 새로 들어왔다: {added}"
    assert not dropped, f"골든에만 남은 낱말이 있다 - --write로 갱신해라: {dropped}"


def test_덤프가_없으면_건너뛴다(tmp_path, monkeypatch):
    """개발 머신에서는 덤프를 sqpack에서 뽑아 두는 것이라 없을 수 있다.

    영어 검사는 덤프를 안 보는 딴 갈래라 여기서 떼어 낸다. 안 떼면 허용목록이
    실물과 어긋난 동안 이 검사가 그 이유로 빨개져서, 무엇이 깨졌는지가 흐려진다.
    """
    monkeypatch.setattr(ko_words, "DUMP", tmp_path / "없다.tsv")
    monkeypatch.setattr(ko_words, "check_latin", lambda write: 0)
    assert ko_words.main([]) == 0


def test_require_dump는_덤프가_없으면_실패한다(tmp_path, monkeypatch, capsys):
    """릴리스 경로와 CI에서는 건너뛰기가 곧 "한 번도 안 돌았다"이다."""
    monkeypatch.setattr(ko_words, "DUMP", tmp_path / "없다.tsv")
    monkeypatch.setattr(ko_words, "check_latin", lambda write: 0)
    assert ko_words.main(["--require-dump"]) == 1
    assert "덤프가 없다" in capsys.readouterr().out
