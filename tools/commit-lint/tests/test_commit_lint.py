"""`Release-Note:` 줄 문법.

**옛 저장소의 C14 시험을 그대로 옮겼다.** 규칙이 재는 것이 커밋 갈래도 경로도
아니라 **줄 자체의 문법**이라, 저장소 구조가 바뀌어도 이 시험은 그대로 산다.

빠진 것은 "언제 이 줄을 요구하나"뿐이다. 옛 저장소는 경로로 물었는데
(`overlay/ko/ko.json`을 건드리면 요구) 그 경로가 이 저장소에 없다.
"""

import pytest

import commit_lint


def problem(note):
    return commit_lint.note_problem(note)


# ------------------------------------------------------------ 명사형 종결


def test_사용자가_읽을_문장은_함으로_끝낸다():
    # 제목은 `~한다`, 노트는 `~함.`이다. 독자가 달라서 문체도 다르다.
    assert problem("바탕화면 바로가기로 게임이 실행되도록 한다")


def test_함_말고_다른_명사형_종결도_통과한다():
    # **`함.`은 명사형의 한 꼴일 뿐이다.** `~고침.`으로 끝나는 트레일러가
    # 이미 이력에 있고(`v5.88.0.1` 노트의 셋째 항목), `함.`만 받으면 그 부류를
    # 다시 쓸 때마다 어미를 억지로 바꿔야 한다.
    assert problem("사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.") is None


def test_마침표가_없으면_명사형이어도_거부한다():
    assert problem("사용 안내의 달라무드 적용 절차를 고침")


def test_받침_없는_서술성_명사도_명사형으로_본다():
    # **N7이 한 번 뒤집힌 자리다.** 사용자가 `v5.93.0.2` 노트를 직접 고치면서
    # `삭제.`·`유지.`로 끝맺었는데 종성 `ㅁ`만 재던 규칙이 셋 다 거부했다.
    # 규칙이 거르려던 것은 제목의 `~한다`체와 존댓말이고 이 둘은 그 대상이 아니다.
    for note in ("적, NPC, 상인 등 분류에서 '근처' 문구 삭제.", "구분이 필요해 그대로 유지."):
        assert problem(note) is None, note


def test_마침표_앞_공백은_종결_판정과_무관하다():
    # 같은 문안의 셋째 항목이 `음성 출력함 .`이었다. 공백 하나로 명사형이
    # 아니게 되는 것은 규칙이 재려던 것과 상관없다.
    assert problem("전체 임무 92개, 개방 41개로 음성 출력함 .") is None


def test_존댓말과_평서형_종결은_그대로_거부한다():
    # 넓히면서 이쪽이 새어 들어오면 규칙이 죽는다.
    for note in (
        "바탕화면 바로가기로 게임이 실행됩니다.",
        "바탕화면 바로가기로 게임이 실행된다.",
        "바탕화면 바로가기로 게임을 실행할까.",
        "바탕화면 바로가기로 게임이 실행되네.",
    ):
        assert problem(note), note


def test_한글이_아닌_글자로_끝나면_거부한다():
    # 넓힌 뒤에도 이 자리는 그대로다. 끝을 안 맺은 줄을 거르는 것이 목적이다.
    assert problem("반경을 100m.")


# ------------------------------------------------------------ 면제


def test_값이_비면_면제가_아니다():
    assert problem("")
    assert problem(None)


def test_없음은_이유를_대야_통과한다():
    assert problem("없음 - 주석만 고침") is None


def test_이유_없는_없음은_거부한다():
    assert problem("없음")


def test_없음_뒤에_구분자가_없으면_거부한다():
    # `없음주석만 고침`처럼 붙여 쓰면 이유를 댄 것으로 보지 않는다.
    assert problem("없음주석만 고침")


def test_이_저장소가_쓴_면제_값이_통과한다():
    # 실제 이력에서 뽑았다. 규칙이 이력과 어긋나면 규칙 쪽을 의심한다.
    for note in ("없음 - 조립 도구", "없음 - 개발 문서라 사용자에게 닿지 않음"):
        assert problem(note) is None, note


# ------------------------------------------------------------ 내부 이름


def test_노트에_내부_이름을_쓰면_거부한다():
    # `Launcher`는 사용자 화면 어디에도 안 뜬다. 사용자가 보는 것은
    # `바탕화면 바로가기`다.
    assert problem("Launcher가 게임과 업데이터를 함께 띄우도록 함.")


def test_백틱_안의_파일_이름은_내부_이름으로_보지_않는다():
    # 사용자가 직접 실행하는 파일이라 노트에 나오는 것이 맞다.
    note = (
        "`FF14AccessibilityInstaller-KR.exe`가 .NET 10 데스크톱 런타임을 "
        "자동으로 내려받아 설치하도록 함."
    )
    assert problem(note) is None


def test_내부_이름_목록이_비어_있지_않다():
    assert commit_lint.NOTE_BANNED


# ------------------------------------------------------------ 트레일러 읽기


def test_마지막에_나온_값을_채택한다():
    message = "제목\n\nRelease-Note: 첫째.\nRelease-Note: 둘째.\n"
    assert commit_lint.trailer_value(message, "Release-Note") == "둘째."


def test_트레일러가_없으면_None이다():
    assert commit_lint.trailer_value("제목만 있다\n", "Release-Note") is None


def test_가위선_아래는_안_본다():
    # git이 커밋할 때 지우는 diff 미리보기라 검사 대상이 아니다.
    message = (
        "제목\n\n"
        "# ------------------------ >8 ------------------------\n"
        "Release-Note: 이건 안 센다.\n"
    )
    body = commit_lint.strip_comments(message)
    assert commit_lint.trailer_value(body, "Release-Note") is None


def test_주석_줄은_안_본다():
    message = "제목\n\n# Release-Note: 주석이다.\nRelease-Note: 진짜다.\n"
    body = commit_lint.strip_comments(message)
    assert commit_lint.trailer_value(body, "Release-Note") == "진짜다."


# ------------------------------------------------------------ 명령줄


def _message(tmp_path, text):
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_규칙에_맞는_줄은_통과한다(tmp_path):
    path = _message(tmp_path, "제목\n\nRelease-Note: 무엇이 어떻게 바뀌도록 함.\n")
    assert commit_lint.main(["commit_lint.py", path]) == 0


def test_규칙에_어긋난_줄은_막는다(tmp_path, capsys):
    path = _message(tmp_path, "제목\n\nRelease-Note: 무엇이 어떻게 바뀝니다.\n")
    assert commit_lint.main(["commit_lint.py", path]) == 1
    assert "Release-Note" in capsys.readouterr().err


def test_줄이_없으면_안_잰_것을_말한다(tmp_path, capsys):
    # **조용히 0으로 끝나면 통과한 것과 안 잰 것이 같아진다.** 어느 커밋이 이
    # 줄을 남겨야 하는지를 정하는 규칙이 이 저장소에 아직 없어서 요구하지는
    # 않지만, 안 쟀다는 사실은 화면에 남긴다.
    path = _message(tmp_path, "제목만 있다\n")
    assert commit_lint.main(["commit_lint.py", path]) == 0
    out = capsys.readouterr().out
    assert "검사할 것이 없다" in out


def test_인자가_틀리면_사용법을_낸다(capsys):
    assert commit_lint.main(["commit_lint.py"]) == 2
    assert "사용법" in capsys.readouterr().err


# ------------------------------------------------------------ 위반 자료형


def test_위반은_번호와_함께_읽힌다():
    # `notes_check`가 이 자료형을 N 번호로 그대로 쓴다.
    assert str(commit_lint.Violation("N7", "무엇이 틀렸다")) == "N7: 무엇이 틀렸다"


@pytest.mark.parametrize("word", ["Launcher", "Dalamud", "repo.json"])
def test_내부_이름은_백틱_밖에서만_걸린다(word):
    assert problem(f"{word}가 어떻게 되도록 함.")
    assert problem(f"`{word}`가 어떻게 되도록 함.") is None
