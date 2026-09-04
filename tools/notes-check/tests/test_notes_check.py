"""릴리스 노트 검사기.

**두 판을 그대로 박아 둔다.** 사용자가 고친 판은 통과해야 하고 발행본은
걸려야 한다 - 규칙이 어느 쪽으로도 미끄러지면 여기서 빨개진다.

**판 번호 `5.88.0.1`은 옛 저장소의 것이고 그대로 둔다.** 이 픽스처의 값어치는
사용자가 실제로 고친 문안이라는 데 있어서, 판 번호를 이 저장소 것으로 바꾸면
근거가 아니라 지어낸 예시가 된다. 주소만 이 저장소 것으로 옮겼다 - 옛 저장소는
지워질 것이라 그대로 두면 픽스처가 없는 곳을 가리킨다.
"""

from __future__ import annotations

import pytest

import notes_check

VERSION = "5.88.0.1"

#: 사용자가 2026-08-22에 직접 고쳐 준 판. **이것이 규칙의 원본이다.**
#: 사용자는 릴리스 페이지에서 복사해 고쳤으므로 백틱과 헤딩 깊이가 렌더링에
#: 씻겨 있었다. 마크업만 되살리고 문장은 한 자도 안 건드렸다.
#:
#: 2026-08-24에 맨 위 `##` 제목 줄을 뺐다. 릴리스 페이지 제목과 같은 정보가
#: 두 번 나오는 것을 사용자가 지적했다.
#:
#: 같은 날 `### 모드 개발자가 검증하지 못한 것` 절이 들어왔다. **문장은 그대로
#: 두고 자리만 옮겼다** - 원본이 미검증이라고 밝힌 줄이 우리 결함과 한 목록에
#: 섞여 있어서, 듣는 사람이 둘을 못 갈랐다.
#:
#: **2026-08-25에 설치 절을 고쳤다.** 사용자용 묶음 압축을 걷으면서 받는 파일과
#: 문서 이름이 바뀌었고, 이 절이 가리키던 셋이 릴리스에 더는 없다.
USER_EDITED = """\
### 설치

`FF14AccessibilityInstaller-KR.exe`를 받아 실행합니다.

설치 방법과 사용법은 아래 주소에서 볼 수 있습니다.

https://github.com/dnz3d4c/FF14-a11y-kr/blob/master/docs/korean/README.ko.md

모드에서 사용하는 단축키 목록은 아래 주소에 있습니다.

https://github.com/dnz3d4c/FF14-a11y-kr/blob/master/docs/korean/keys.md

### v5.88.0.1 변경사항

- 바탕화면 바로가기로 게임과 KR 달라무드 업데이터가 실행되도록 함.
- 설치 프로그램이 .NET 10 데스크톱 런타임을 자동으로 내려받아 설치하도록 함.
- 사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.

모드 변경사항: 없음.

### 준비물

- 한국 서버 파이널 판타지 14 계정과 클라이언트
- 스크린 리더(NVDA등)

.NET 10 데스크톱 런타임과 KR 달라무드 업데이터, vnavmesh는 설치 프로그램이 직접 \
내려받아 설치합니다. vnavmesh는 설치 전 설치 여부를 묻는 창이 표시됩니다.

### 업데이트 방법

`FF14AccessibilityInstaller-KR.exe`를 실행합니다.

설치 프로그램은 새 버전이 있는지 확인하고 새 버전 설치를 묻는 대화상자가 표시됩니다. \
[예]를 선택하면 프로그램이 업데이트됩니다.

### 알려진 제한사항

- 방향 안내에 할당된 `N` 키가 게임의 제작 메뉴와 겹칩니다
- 기본 단축키 셋(`Ctrl+F`, `Shift+Home`, `Alt+Home`)이 동작하지 않습니다
- 알림 수락 안내에서 키 이름이 독일어(`Strg+F12`)로 들립니다
- 캐릭터 생성 화면의 외모 묘사는 한국어로 음성 출력되지 않습니다.

자세한 내용과 대처 방법은 사용 안내의 문제 해결 절에 있습니다.

### 모드 개발자가 검증하지 못한 것

- 장판 경고음은 기본으로 꺼져 있습니다. 장판 모양 인식이 게임에서 아직 최종 확인되지 않았습니다

### 라이선스

AGPL-3.0. 원본은 derbruedi/ff14-accessibility이고, 이 저장소는 한국 서버용으로 옮긴 것입니다.

※ 아래 나머지 파일은 설치 프로그램과 Dalamud가 자동 업데이트에 사용합니다. \
직접 받을 필요는 없습니다.
"""

#: 실제로 나간 v5.88.0.1 노트. **이것이 고쳐야 할 판이다.**
PUBLISHED = """\
FF14 접근성 모드 (한국 서버용) v5.88.0.1 입니다. \
파이널 판타지 14를 한국 서버에서 스크린 리더로 플레이할 수 있습니다.

## 설치

`FF14Accessibility-KR-Setup.zip`을 받아 압축을 풀고, \
폴더 안의 `FF14AccessibilityInstaller-KR.exe`를 실행합니다.

## 이번 판에서 바뀐 것

설치할 때 사용자가 직접 하던 일 둘을 설치 프로그램이 대신합니다.

- **바탕화면 바로가기로 게임과 KR 달라무드 업데이터가 실행되도록 함.**
- **설치 프로그램이 .NET 10 데스크톱 런타임을 자동으로 내려받아 설치하도록 함.**
- **사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.**

모드 자체는 바뀌지 않았습니다. 버전만 v5.88.0.1로 올랐습니다.

## 준비물

- 한국 서버 파이널 판타지 14 계정과 클라이언트
- NVDA 등 스크린 리더

## 알려진 제한

- 캐릭터 생성 화면의 외모 묘사는 아직 한국어로 옮기지 않았습니다

## 문제를 알릴 곳

[이슈](https://github.com/dnz3d4c/FF14-a11y-kr/issues)로 알려 주시면 됩니다.

## 라이선스

AGPL-3.0. 원본은 \
[derbruedi/ff14-accessibility](https://github.com/derbruedi/ff14-accessibility)이고, \
이 저장소는 한국 서버용으로 옮긴 것입니다.

※ 아래 나머지 파일은 설치 프로그램과 Dalamud가 자동 업데이트에 사용합니다. \
직접 받을 필요는 없습니다.
"""


#: `USER_EDITED`의 변경사항 절 본문. 절을 통째로 갈아 끼우는 테스트가 셋이라
#: 상수로 뺀다. **`swap`이 이 문자열을 못 찾으면 실패한다** - 픽스처를 고치다
#: 여기가 갈리면 그 셋이 조용히 통과한다.
CHANGES_BODY = """\
- 바탕화면 바로가기로 게임과 KR 달라무드 업데이터가 실행되도록 함.
- 설치 프로그램이 .NET 10 데스크톱 런타임을 자동으로 내려받아 설치하도록 함.
- 사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.

모드 변경사항: 없음."""


def codes(text: str, version: str = VERSION) -> set[str]:
    return {v.code for v in notes_check.check(text, version)}


def swap(old: str, new: str, text: str = USER_EDITED) -> str:
    """통과하는 판에서 한 자리만 어긋뜨린다. **못 찾으면 실패다** - 픽스처를
    고치다 대상 문자열이 사라지면 그 테스트가 조용히 통과하기 때문이다."""
    if old not in text:
        raise AssertionError(f"픽스처에 `{old}`가 없다. 테스트를 같이 고쳐라")
    return text.replace(old, new, 1)


# ------------------------------------------------------------------ 두 판


def test_사용자가_고친_판이_통과한다():
    assert notes_check.check(USER_EDITED, VERSION) == []


def test_발행본이_걸린다():
    found = codes(PUBLISHED)
    # 제목·절 구성·제목 깊이·링크·굵게 남발이 전부 다르다. **N7·N8은 여기서
    # 안 걸린다** - 절을 전부 `##`로 써서 변경사항 절 자체가 안 잡히고, 그것을
    # 먼저 말하는 것이 N3다.
    assert {"N2", "N3", "N4", "N9", "N10", "N11"} <= found


def test_본이_검사를_통과한다():
    """본과 규칙이 갈리는 것을 막는다. 사람이 채우는 자리는 여기서 채운다."""
    text = notes_check.render(VERSION)
    text = text.replace("{{변경 항목}}", "- 무엇이 어떻게 바뀌도록 함.")
    text = text.replace("{{한국어 수정 목록}}", "- 안내 문장 무엇을 게임 표현으로 맞춤.")
    text = text.replace("{{모드 변경 목록}}", "없음.")
    text = text.replace("{{알려진 제한사항}}", "- 무엇이 아직 안 됩니다")
    text = text.replace("{{미검증 목록}}", "- 무엇이 게임에서 아직 확인되지 않았습니다")
    assert notes_check.check(text, VERSION) == []


# ------------------------------------------------------------------ 명세 대조
#
# **명세는 `docs/dev/release-notes-rules.md`가 갖는다.** 검사기가 그 표를 읽어
# 목록을 내므로 두 벌이 안 생긴다. 갈리는 것을 여기서 붙잡는다.


def test_규칙_목록을_문서에서_읽는다():
    listed = notes_check.rules()
    assert [code for code, _ in listed] == [f"N{n}" for n in range(1, len(listed) + 1)]
    assert all(what.strip() for _, what in listed)


def test_문서와_검사기의_번호가_같다():
    # 한쪽만 늘면 여기가 빨개진다. 명세를 코드에 베끼지 않는 값이 이것이다.
    assert notes_check.rule_gaps() == []


def test_검사기가_내는_번호를_자기_소스에서_긁는다():
    emitted = notes_check.emitted_codes()
    assert {"N1", "N7", "N21", "N26"} <= emitted


def test_rules가_목록을_화면에_낸다(capsys):
    assert notes_check.main(["--rules"]) == 0
    out = capsys.readouterr().out
    assert "N1:" in out and "N26:" in out


def test_규칙_표를_못_읽으면_소리를_낸다(tmp_path, capsys):
    # 문서 형식이 바뀌어 표를 못 읽으면 조용히 빈 목록을 내면 안 된다.
    empty = tmp_path / "rules.md"
    empty.write_text("표가 없다\n", encoding="utf-8")
    assert notes_check.rules(empty) == ()


# ------------------------------------------------------------------ 규칙별


def test_N1_BOM이_붙으면_걸린다():
    text, found = notes_check.decode(("﻿" + USER_EDITED).encode("utf-8"))
    assert [v.code for v in found] == ["N1"]
    # BOM을 뗀 나머지는 그대로 검사한다 - 첫 줄이 제목으로 되살아나야 한다.
    assert notes_check.check(text, VERSION) == []


def test_N1_UTF8이_아니면_걸린다():
    _, found = notes_check.decode(USER_EDITED.encode("cp949"))
    assert [v.code for v in found] == ["N1"]


def test_N2_본문에_상위_제목이_있으면_걸린다():
    """릴리스 페이지 제목과 같은 정보라 본문에 두지 않는다."""
    with_title = "## FF14 접근성 모드 (한국 서버용) v5.88.0.1\n\n" + USER_EDITED
    assert "N2" in codes(with_title)


def test_N2_절_하나가_상위로_올라가도_걸린다():
    assert "N2" in codes(swap("### 라이선스", "## 라이선스"))


def test_N2_첫_줄이_설치_절이_아니면_걸린다():
    assert "N2" in codes(swap("### 설치", "### 시작하기"))


def test_N3_절을_빠뜨리면_걸린다():
    assert "N3" in codes(swap("### 준비물\n", ""))


def test_N3_절_순서를_바꾸면_걸린다():
    swapped = swap("### 준비물", "### 업데이트 방법")
    swapped = swap(
        "### 업데이트 방법\n\n`FF14AccessibilityInstaller",
        "### 준비물\n\n`FF14AccessibilityInstaller",
        swapped,
    )
    assert "N3" in codes(swapped)


def test_N3_모르는_절을_넣으면_걸린다():
    """열거 밖은 통과가 아니라 위반이다. 이슈 절이 실제로 그렇게 되살아났다."""
    extra = "### 문제를 알릴 곳\n\n이슈로 알려 주시면 됩니다.\n\n### 라이선스"
    assert "N3" in codes(swap("### 라이선스", extra))


def test_N4_깊이가_다르면_걸린다():
    assert "N4" in codes(swap("### 준비물", "#### 준비물"))


def test_N4_개수를_절_목록에서_센다():
    # **여기 숫자를 적지 않는다.** 명세 문서가 한때 여섯이라고 적어 둔 채로
    # 절이 일곱이 됐고, 그 숫자를 아무도 안 고쳤다.
    found = [
        v for v in notes_check.check(swap("### 준비물", "#### 준비물"), VERSION) if v.code == "N4"
    ]
    assert f"`###` {len(notes_check.SECTION_NAMES)}개" in found[0].message


def test_N5_지난_판_번호가_남으면_걸린다():
    assert "N5" in codes(swap("### v5.88.0.1 변경사항", "### v5.88.0.0 변경사항"))


def test_N6_자리표시자가_남으면_걸린다():
    assert "N6" in codes(swap("스크린 리더(NVDA등)", "{{스크린 리더}}"))


def test_N7_항목이_명사형이_아니면_걸린다():
    assert "N7" in codes(swap("실행되도록 함.", "실행되도록 고쳤습니다."))


def test_N7_항목에_내부_이름을_쓰면_걸린다():
    assert "N7" in codes(swap("바탕화면 바로가기로", "Launcher가"))


def test_N7_항목에_없음을_쓰면_걸린다():
    """트레일러의 `없음 - <이유>` 면제는 노트 항목에서는 통하지 않는다."""
    assert "N7" in codes(
        swap(
            "- 바탕화면 바로가기로 게임과 KR 달라무드 업데이터가 실행되도록 함.",
            "- 없음 - 주석만 고침",
        )
    )


def test_N7_받침_없는_서술성_명사가_통과한다():
    """**N7이 한 번 뒤집힌 자리다.** 종결어미만 막고 마침표 앞 공백은 무시한다."""
    for tail in ("문구 삭제.", "그대로 유지.", "음성 출력함 ."):
        assert "N7" not in codes(swap("실행되도록 함.", tail)), tail


def test_N8_모드_변경_줄이_없으면_걸린다():
    assert "N8" in codes(swap("모드 변경사항: 없음.\n\n", ""))


def test_N8_모드_변경_줄이_둘이면_걸린다():
    assert "N8" in codes(swap("모드 변경사항: 없음.", "모드 변경사항: 없음.\n모드 변경사항: 없음."))


def test_N8_어중간한_값이면_걸린다():
    assert "N8" in codes(swap("모드 변경사항: 없음.", "모드 변경사항: 있음."))


def test_N8_없음인데_목록이_붙으면_걸린다():
    assert "N8" in codes(
        swap("모드 변경사항: 없음.", "모드 변경사항: 없음.\n- 무엇이 바뀌도록 함.")
    )


def test_N8_비었는데_목록이_없으면_걸린다():
    assert "N8" in codes(swap("모드 변경사항: 없음.", "모드 변경사항:"))


def test_N8_비고_목록이_붙으면_통과한다():
    assert (
        notes_check.check(
            swap("모드 변경사항: 없음.", "모드 변경사항:\n- 무엇이 어떻게 말하도록 함."), VERSION
        )
        == []
    )


def test_N8_모드만_바뀐_판이_통과한다():
    # **모드만 바뀐 판은 `모드 변경사항:` 줄 위에 둘 항목이 없다.** 처음 판은
    # 위가 비면 무조건 "항목보다 앞에 있다"로 걸어서, `v5.91.0.1`처럼 한국어
    # 문장만 고친 판의 노트를 통과시킬 방법이 아예 없었다.
    모드만 = swap(CHANGES_BODY, "모드 변경사항:\n- 안내 문장의 낱말을 게임이 쓰는 표현으로 맞춤.")
    assert notes_check.check(모드만, VERSION) == []


def test_N8_줄만_있고_변경_항목이_없으면_걸린다():
    # 완화가 여는 것은 **아래에 목록이 있는 경우**뿐이다. 위도 아래도 비면
    # 이번 판이 무엇을 바꿨는지가 노트에 한 줄도 없다.
    빈판 = swap(CHANGES_BODY, "모드 변경사항: 없음.")
    assert "N8" in codes(빈판)


def test_N19_한국어_수정_표지가_통과한다():
    # 한국어 문장만 고친 판을 `모드 변경사항:` 아래에 넣으면 원본 모드가 바뀐
    # 것으로 읽힌다. 표지를 갈라서 원본이 안 바뀌었다는 것이 그대로 들리게 한다.
    갈림 = swap(
        CHANGES_BODY,
        "한국어 번역 문장 수정:\n\n"
        "- 안내 문장의 낱말을 게임이 쓰는 표현으로 맞춤.\n\n"
        "모드 변경사항: 없음.",
    )
    assert notes_check.check(갈림, VERSION) == []


def test_N19_값을_적으면_걸린다():
    assert "N19" in codes(
        swap(CHANGES_BODY, "한국어 번역 문장 수정: 있음.\n\n모드 변경사항: 없음.")
    )


def test_N19_아래에_목록이_없으면_걸린다():
    assert "N19" in codes(swap(CHANGES_BODY, "한국어 번역 문장 수정:\n\n모드 변경사항: 없음."))


def test_N19_모드_줄보다_뒤면_걸린다():
    # 받는 방법을 가르는 신호(N8)가 절의 마지막에 온다. 새 표지가 그 뒤로
    # 가면 신호가 목록 한가운데에 묻힌다.
    뒤집힘 = swap(
        CHANGES_BODY,
        "모드 변경사항:\n\n- 무엇이 어떻게 말하도록 함.\n\n"
        "한국어 번역 문장 수정:\n\n- 안내 문장의 낱말을 게임이 쓰는 표현으로 맞춤.",
    )
    assert "N19" in codes(뒤집힘)


def test_N19_표지가_둘이면_걸린다():
    둘 = swap(
        CHANGES_BODY,
        "한국어 번역 문장 수정:\n\n- 안내 문장의 낱말을 게임이 쓰는 표현으로 맞춤.\n\n"
        "한국어 번역 문장 수정:\n\n- 또 무엇을 맞춤.\n\n모드 변경사항: 없음.",
    )
    assert "N19" in codes(둘)


def test_N19_항목도_명사형이어야_한다():
    # 새 표지 아래도 변경 항목이라 N7이 그대로 본다. 표지를 가른 것이지
    # 문체를 가른 것이 아니다.
    서술형 = swap(
        CHANGES_BODY,
        "한국어 번역 문장 수정:\n\n"
        "- 안내 문장의 낱말을 게임 표현으로 고쳤습니다.\n\n"
        "모드 변경사항: 없음.",
    )
    assert "N7" in codes(서술형)


def test_N3_미검증_절이_빠지면_걸린다():
    assert "N3" in codes(swap("### 모드 개발자가 검증하지 못한 것\n", ""))


def test_N16_미검증_절이_산문으로_시작하면_걸린다():
    assert "N16" in codes(
        swap(
            "### 모드 개발자가 검증하지 못한 것\n\n- 장판 경고음은",
            "### 모드 개발자가 검증하지 못한 것\n\n"
            "아래는 원본 개발자의 표시입니다.\n\n"
            "- 장판 경고음은",
        )
    )


def test_N9_인라인_링크가_있으면_걸린다():
    assert "N9" in codes(
        swap(
            "derbruedi/ff14-accessibility이고",
            "[derbruedi/ff14-accessibility](https://github.com/derbruedi/ff14-accessibility)이고",
        )
    )


def test_N10_항목을_통째로_굵게_하면_걸린다():
    assert "N10" in codes(
        swap(
            "- 사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.",
            "- **사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.**",
        )
    )


def test_N10_한_낱말만_굵게_하면_통과한다():
    assert (
        notes_check.check(
            swap("게임과 KR 달라무드 업데이터가", "게임과 **KR 달라무드 업데이터**가"), VERSION
        )
        == []
    )


def test_N11_한_절에_굵게가_둘이면_걸린다():
    twice = swap("게임과 KR 달라무드 업데이터가", "게임과 **KR 달라무드 업데이터**가")
    twice = swap(
        ".NET 10 데스크톱 런타임을 자동으로", "**.NET 10 데스크톱 런타임**을 자동으로", twice
    )
    assert "N11" in codes(twice)


def test_N11_기울임이_있으면_걸린다():
    assert "N11" in codes(swap("게임과 KR 달라무드", "게임과 *KR* 달라무드"))


def test_N12_백틱_안_한글은_걸린다():
    assert "N12" in codes(
        swap("모드에서 사용하는 단축키 목록은", "모드에서 사용하는 `단축키 목록`은")
    )


def test_N12_허용_목록이_비어_있다():
    # 릴리스에 올라가는 이름은 전부 ASCII다. 배포 폴더 안의 한글 이름
    # (`사용 안내.md`)은 릴리스 자산이 아니라 노트에 쓰면 못 찾는다.
    assert notes_check.BACKTICK_HANGUL_OK == ()


def test_N13_한다체가_섞이면_걸린다():
    assert "N13" in codes(swap("프로그램이 업데이트됩니다.", "프로그램이 업데이트된다."))


def test_N14_내부_이름이_본문에_있으면_걸린다():
    assert "N14" in codes(swap("설치 프로그램은 새 버전이", "Installer는 새 버전이"))


def test_N14_Dalamud는_보충_줄_밖에서_걸린다():
    assert "N14" in codes(swap("설치 프로그램은 새 버전이", "Dalamud는 새 버전이"))


def test_N15_보충_줄이_없으면_걸린다():
    assert "N15" in codes(swap("※ 아래 나머지 파일은", "아래 나머지 파일은"))


def test_N15_보충_줄이_둘이면_걸린다():
    assert "N15" in codes(
        swap("※ 아래 나머지 파일은", "※ 무엇을 더 적습니다.\n\n※ 아래 나머지 파일은")
    )


def test_N16_절이_도입_문단으로_시작하면_걸린다():
    assert "N16" in codes(
        swap("### 준비물\n\n- 한국 서버", "### 준비물\n\n다음이 미리 있어야 합니다.\n\n- 한국 서버")
    )


def test_N16_변경사항_절이_도입_문단으로_시작하면_여전히_걸린다():
    # N8을 풀면서 변경사항 절의 첫 줄에 `모드 변경사항:`을 열었다. **연 것은
    # 그 줄 하나지 산문이 아니다** - 산문까지 같이 열리면 이 규칙이 그 절에서만
    # 죽고, 죽은 것을 아무도 안 본다.
    산문 = swap(CHANGES_BODY, "이번 판은 안내 문장을 고쳤습니다.\n\n" + CHANGES_BODY)
    assert "N16" in codes(산문)


def test_N17_항목_둘이_한_줄로_붙으면_걸린다():
    # 2026-08-24에 실제로 그렇게 나갔다. 지난 판 넷에 미검증 줄을 소급해
    # 넣는 스크립트가 절 제목 뒤 줄바꿈을 먹어서, 새 항목과 원래 첫 항목이
    # 한 줄이 됐다. **검사기가 그것을 통과시켰다.**
    붙은것 = swap(
        "- 한국 서버 파이널 판타지 14 계정과 클라이언트",
        "- 한국 서버 파이널 판타지 14 계정과 클라이언트- 스크린 리더",
    )
    assert "N17" in codes(붙은것)


def test_N17_항목_사이의_붙임표는_안_걸린다():
    # 오탐이 잡음이 되면 그날로 죽는 장치다. 재는 것은 **앞에 공백이 없는**
    # 표지뿐이라, 문장 안의 붙임표는 안 걸린다.
    성한것 = swap(
        "- 스크린 리더(NVDA등)",
        "- 스크린 리더(NVDA등) - 화면을 소리로 읽어 주는 프로그램",
    )
    assert "N17" not in codes(성한것)


def test_N18_소리로_갈리는_낱말이_걸린다():
    # 2026-08-24에 `v5.91`이 그렇게 나갔다. 노트가 `다리나 고가 아래에 선
    # 목표`라고 썼는데, 이 게임에서 `다리`는 장비 부위(`Legs`)이고 `고가`는
    # 소리로 `高價`와 갈린다. **듣는 사람이 무슨 말인지 모르겠다고 했다.**
    for 낱말 in ("다리", "고가"):
        assert "N18" in codes(swap("- 스크린 리더(NVDA등)", f"- {낱말} 아래에 선 목표"))


def test_N18_모드가_안_쓰는_표현이_걸린다():
    # 같은 판에서 노트가 `위가 막힌 곳`을 썼는데 모드는 `위쪽이 막힌 곳`으로
    # 발화한다. **듣는 말과 읽는 말이 갈라진 것을 아무도 안 봤다.**
    assert "N18" in codes(swap("- 스크린 리더(NVDA등)", "- 목표가 위가 막힌 곳에 있음"))


def test_N18_대체어를_알려준다():
    # 목록이 규칙의 전부라 무엇으로 바꿀지 같이 주지 않으면 다음 사람이
    # 또 지어낸다. 이 검사가 잡아 놓고 답을 안 주면 절반만 한 것이다.
    문제 = [
        v
        for v in notes_check.check(swap("- 스크린 리더(NVDA등)", "- 다리 아래"), VERSION)
        if v.code == "N18"
    ]
    assert "위쪽이 막힌 곳" in 문제[0].message


def test_N18_목록을_lexicon에서_읽는다():
    # 목록이 도구마다 따로 있으면 새 판정이 어디로 갈지가 안 정해진다.
    assert notes_check.NOTE_KO_BANNED
    assert set(notes_check.NOTE_KO_BANNED) == {
        entry.bad for entry in notes_check.ko_lexicon.entries("note")
    }


def test_N18_성한_본은_안_걸린다():
    # 오탐이 잡음이 되면 그날로 죽는 장치다.
    assert "N18" not in codes(USER_EDITED)


def test_N18_낱말_한가운데는_안_걸린다():
    # **처음 판이 이것을 못 봤다.** 부분 문자열로 재서 이미 나간 판 둘을
    # 빨갛게 만들었다 - `기다리는지`의 `다리`와 `경고가`의 `고가`다.
    # **틀린 것은 옛 판이 아니라 검사기였다.**
    for 문장 in (
        "- 얼마나 기다리는지가 안내에서 빠져 있던 것을 고쳤습니다",
        "- 전투 경고가 스크린 리더와 별개로 나가도록 함.",
        "- 범위가 넓은 장판을 알리도록 함.",
    ):
        assert "N18" not in codes(swap("- 스크린 리더(NVDA등)", 문장))


def test_N18_조사가_붙어도_걸린다():
    # 앞을 막는다고 뒤까지 막으면 `다리를`·`고가가`를 놓친다.
    for 문장 in ("- 다리를 지나쳐 올라감.", "- 고가 아래에 선 목표"):
        assert "N18" in codes(swap("- 스크린 리더(NVDA등)", 문장))


def test_N20_걷어낸_자산을_지목하면_걸린다():
    # 노트는 사람이 본을 복사해 쓰는 자리라 옛 판 문구가 그대로 따라온다.
    for 이름 in notes_check.DROPPED_ASSETS:
        assert "N20" in codes(
            swap("`FF14AccessibilityInstaller-KR.exe`를 받아 실행합니다.", f"`{이름}`을 받습니다.")
        ), 이름


def test_N20_주소_안의_경로는_안_걸린다():
    # 파일을 받으라는 것이 아니라 문서를 열라는 것이라 걸리면 안 된다.
    assert "N20" not in codes(USER_EDITED)


# ------------------------------------------------------------------ 본 자체


def test_본의_자리표시자가_여섯이다():
    """`render()`가 채우는 것과 사람이 채우는 것의 경계. 늘리면 문서도 같이 고친다."""
    assert notes_check.placeholders(notes_check.template()) == {
        "버전",
        "변경 항목",
        "한국어 수정 목록",
        "모드 변경 목록",
        "알려진 제한사항",
        "미검증 목록",
    }


def test_render가_버전만_채운다():
    text = notes_check.render(VERSION)
    assert "{{버전}}" not in text
    assert notes_check.placeholders(text) == {
        "변경 항목",
        "한국어 수정 목록",
        "모드 변경 목록",
        "알려진 제한사항",
        "미검증 목록",
    }


def test_본이_이_저장소의_문서_주소를_가리킨다():
    # 옛 저장소 주소가 남으면 받는 사람이 없는 곳을 연다.
    text = notes_check.template()
    assert notes_check.release_manifest.GUIDE_DOC_URL in text
    assert notes_check.release_manifest.KEYS_DOC_URL in text


# ------------------------------------------- 원본 노트 대비 커버리지 (N21)
#
# `v5.92`가 원본 절 넷 중 `## Werkzeug`를 통째로 빠뜨린 채 나갔다. 그때 검사기는
# 초록이었다 - 우리 노트 안만 보고 원본을 안 봤기 때문이다.

UP_V592 = """## Ziele auf Erhöhungen erreichen

Ein Quest-Objekt war nicht erreichbar. Behoben.

Dazu:
- Das Ankunftsmaß brach kurze Brücken ab. Behoben.
- Steht ein Ziel höher, sagt die Ansage das mit.

## Drei Tastenbelegungen waren nie verdrahtet

`Strg+F` löste nie aus.

## Werkzeug

`tools/navmesh-gaps` liegt jetzt im Repo.
"""

UP_MIT_ZITAT = """## Reihenfolge

Jeder Schritt sagt dir, wo du stehst:

> Gegner, jetzt 3 von 21. Zwischen Händler und Verbündete.

Am Anfang heißt es nur „Vor Alles.".
"""


def _ours(items: list[str]) -> str:
    """변경사항 절을 통째로 갈아 끼운 우리 노트.

    `swap`을 쓰면 원본에 있던 항목 셋이 남아서 세는 수가 어긋난다.
    """
    out: list[str] = []
    in_changes = False
    for line in USER_EDITED.splitlines():
        if line.startswith("### "):
            in_changes = line.strip() == f"### v{VERSION} 변경사항"
            out.append(line)
            if in_changes:
                out += ["", "모드 변경사항:", ""] + [f"- {t}" for t in items] + [""]
            continue
        if not in_changes:
            out.append(line)
    return "\n".join(out) + "\n"


def test_N21_원본_절_수보다_적으면_걸린다():
    """원본이 절 셋에 항목 둘이니 정보 단위가 다섯인데 우리가 둘만 냈다."""
    ours = _ours(["첫째 바뀜.", "둘째 바뀜."])
    codes_ = [v.code for v in notes_check.coverage(ours, UP_V592, VERSION)]
    assert "N21" in codes_


def test_N21_원본을_다_덮으면_개수는_통과한다():
    """개수가 차면 N21은 안 뜬다. 되묻기(N23)는 그와 무관하게 판마다 뜬다."""
    ours = _ours([f"{n}번째 바뀜." for n in range(1, 6)])
    codes_ = [v.code for v in notes_check.coverage(ours, UP_V592, VERSION)]
    assert "N21" not in codes_
    assert "N23" in codes_


def test_N23_메시지가_원본_절_이름을_돌려준다():
    """개수만 알려 주면 무엇을 빠뜨렸는지 사람이 못 찾는다."""
    bad = notes_check.coverage(_ours(["하나 바뀜."]), UP_V592, VERSION)
    text = "\n".join(v.message for v in bad)
    assert "Werkzeug" in text
    assert "Drei Tastenbelegungen waren nie verdrahtet" in text


def test_N23은_개수가_넉넉해도_뜬다():
    """`v5.92` 재현 - 항목 14개에 원본 단위 10이라 개수로는 절 누락이 안 잡힌다.

    도구 절 대응 항목 하나를 빼도 13 > 10이다. 되묻기를 개수 조건에 묶으면
    그 판이 그대로 통과한다.
    """
    ours = _ours([f"{n}번째 바뀜." for n in range(1, 15)])
    codes_ = [v.code for v in notes_check.coverage(ours, UP_V592, VERSION)]
    assert codes_ == ["N23"]


def test_N22_원본이_든_발화_예시를_되묻는다():
    """개수가 충분해도 원본이 인용한 실제 발화가 빠지면 알린다 - `v5.93`이 그렇게 나갔다."""
    ours = _ours([f"{n}번째 바뀜." for n in range(1, 9)])
    bad = notes_check.coverage(ours, UP_MIT_ZITAT, VERSION)
    codes_ = [v.code for v in bad]
    assert "N22" in codes_
    text = "\n".join(v.message for v in bad)
    assert "Gegner, jetzt 3 von 21" in text
    assert "Vor Alles." in text


def test_N22는_인용이_없으면_안_뜬다():
    ours = _ours([f"{n}번째 바뀜." for n in range(1, 6)])
    assert "N22" not in [v.code for v in notes_check.coverage(ours, UP_V592, VERSION)]


def test_되묻기만_선언으로_넘긴다():
    """N21은 선언으로 못 넘긴다 - 개수 미달은 사람이 봤다고 사라지는 사실이 아니다."""
    assert set(notes_check.ASK_CODES) == {"N22", "N23"}
    assert "N21" not in notes_check.ASK_CODES


def test_원본_단위를_센다():
    units = notes_check.upstream_units(UP_V592)
    assert units["sections"] == [
        "Ziele auf Erhöhungen erreichen",
        "Drei Tastenbelegungen waren nie verdrahtet",
        "Werkzeug",
    ]
    assert units["items"] == 2
    assert units["quotes"] == []


def test_원본_인용을_뽑는다():
    units = notes_check.upstream_units(UP_MIT_ZITAT)
    assert "Gegner, jetzt 3 von 21. Zwischen Händler und Verbündete." in units["quotes"]
    assert "Vor Alles." in units["quotes"]


def test_원본_꼬리_문단은_절로_안_센다():
    """`---` 아래의 전체 변경 이력 안내는 이번 판의 변경이 아니다."""
    text = UP_V592 + "\n---\n\nVoller Änderungsverlauf: `STATUS.md` im Repo.\n"
    assert (
        notes_check.upstream_units(text)["sections"]
        == notes_check.upstream_units(UP_V592)["sections"]
    )


@pytest.mark.parametrize("closing", ["“", "”", '"'])
def test_독일어_인용을_닫는_부호_셋을_다_받는다(closing):
    """**표준 부호가 빠져 있었다.**

    독일어 표준 인용은 `„…“`(U+201E … U+201C)인데 닫는 문자 클래스에
    U+201C가 없어서, 원본이 정식으로 쓴 예시를 통째로 못 봤다. 업스트림이
    독일어로 개발되므로 이 부호가 기본형이다. 이 검사가 있는 이유가 `v5.93`이
    발화 예시를 잃은 것인데, 못 보면 검사가 조용히 0건을 돌려준다.
    """
    text = f"## Neu\n\nDas klingt so: „Gegner, jetzt 3 von 21.{closing}\n"
    assert notes_check.upstream_units(text)["quotes"] == ["Gegner, jetzt 3 von 21."]


def test_빈_원본_노트는_조용히_통과하지_않는다():
    """`gh`가 실패해도 리다이렉트가 빈 파일을 남긴다. 그 모양이 실제로 나온다."""
    ours = _ours(["하나 바뀜."])
    codes_ = [v.code for v in notes_check.coverage(ours, "", VERSION)]
    assert codes_ == ["N21"]


def test_절_없는_원본은_되묻기도_안_낸다():
    """깨진 입력으로 되묻기 목록을 내면 사람이 빈 목록을 대조했다고 넘긴다."""
    bad = notes_check.coverage(_ours(["하나 바뀜."]), "본문만 있고 절이 없다\n", VERSION)
    assert [v.code for v in bad] == ["N21"]


def test_N21은_절_수만_센다():
    """항목까지 세면 절충 기준으로 제대로 쓴 판이 걸린다.

    `v5.89`가 절 5에 항목 12인 원본을 14항목으로 옮겼는데, 절+항목 17을 기준으로
    삼으면 그 판이 미달로 걸렸다. 우리 편집 기준은 원본 항목을 다 옮기는 것이
    아니므로 그 자리가 곧 무시된다.
    """
    ours = _ours([f"{n}번째 바뀜." for n in range(1, 5)])  # 항목 4 > 절 3, 원본 항목 2+절 3=5
    assert "N21" not in [v.code for v in notes_check.coverage(ours, UP_V592, VERSION)]


def test_개정판은_커버리지를_통째로_건너뛴다(tmp_path, capsys):
    """네 번째 마디만 오르는 판은 원본이 안 바뀌어서 옮길 절이 없다.

    `N21`은 선언(`--upstream-acked`)으로 못 넘기는 위반이라, 개정판을 첫 판과
    같이 재면 **같은 절을 판마다 다시 옮기라고 요구한다.** `v5.93.0.1`이 실제로
    거기서 막혔다.
    """
    notes = tmp_path / f"{VERSION}.md"
    notes.write_text(_ours(["하나 바뀜."]), encoding="utf-8")
    up = tmp_path / "up.md"
    up.write_text(UP_V592, encoding="utf-8")

    rc = notes_check.main([str(notes), "--upstream-notes", str(up), "--upstream-unchanged"])

    assert rc == 0
    assert "N21" not in capsys.readouterr().err


def test_개정판이_건너뛴_이유를_화면에_남긴다(tmp_path, capsys):
    """조용히 넘기면 원본을 안 본 판과 다 옮긴 판이 화면에서 같아진다."""
    notes = tmp_path / f"{VERSION}.md"
    notes.write_text(_ours(["하나 바뀜."]), encoding="utf-8")
    up = tmp_path / "up.md"
    up.write_text(UP_V592, encoding="utf-8")

    notes_check.main([str(notes), "--upstream-notes", str(up), "--upstream-unchanged"])

    out = capsys.readouterr().out
    assert "건너뜀" in out
    assert "N21" in out


def test_플래그가_없으면_개정판도_그대로_걸린다(tmp_path, capsys):
    """면제는 부르는 쪽이 판단한다. 검사기가 알아서 봐주지 않는다."""
    notes = tmp_path / f"{VERSION}.md"
    notes.write_text(_ours(["하나 바뀜."]), encoding="utf-8")
    up = tmp_path / "up.md"
    up.write_text(UP_V592, encoding="utf-8")

    rc = notes_check.main([str(notes), "--upstream-notes", str(up)])

    assert rc == 1
    assert "N21" in capsys.readouterr().err


# ------------------------------------------------- N24·N25
#
# **둘 다 규칙이 이미 문서에 있었는데 기계가 안 봐서 다섯 판 연속 새어
# 나간 자리다.** N24는 `v5.93.0.2`에서 정한 `음성 출력`이 되돌아간 것을,
# N25는 규칙에도 본에도 없는 세 번째 표지 줄이 생긴 것을 잡는다.


def test_N24_모드가_내는_소리를_알려_줌으로_적으면_걸린다():
    assert "N24" in codes(
        swap(
            "- 사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.",
            "- 던전 분류가 길의 지점을 알려 줌.",
        )
    )


def test_N24_말함과_들림_계열도_걸린다():
    for 문장 in (
        "- 오르내리는 높이를 말함.",
        "- 오르내리는 높이를 말하게 됨.",
        "- 번호를 먼저 말하고 종류를 이어 붙임.",
        "- 어디에서 오르내리는지는 말하지 않음.",
        "- 다음처럼 들림.",
        "- 분류 이름이 들리고 개수가 이어짐.",
        "- 지점을 알려 주는데 종류는 넷임.",
    ):
        assert "N24" in codes(
            swap("- 사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.", 문장)
        ), 문장


def test_N24_인용하는_라고_말함은_통과한다():
    """`v5.93.0.1`이 `…놓기라고 말함`으로 나갔고 사용자가 승인했다.

    무엇을 발화하는지 인용하는 자리는 살아 있고, 동작을 서술하는 자리만
    `음성 출력`으로 간다.
    """
    assert "N24" not in codes(
        swap(
            "- 사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.",
            "- 줄을 놓을 때 `놓기`라고 말함.",
        )
    )


def test_N24_대체어를_알려준다():
    found = [
        v.message
        for v in notes_check.check(
            swap(
                "- 사용 안내의 달라무드 적용 절차를 실제 동작에 맞게 고침.",
                "- 던전 분류가 길의 지점을 알려 줌.",
            ),
            VERSION,
        )
        if v.code == "N24"
    ]
    assert found and "음성 출력함" in found[0]


def test_N24_변경_항목_밖은_안_본다():
    """산문 절은 습니다체라 `알려 줍니다`가 정상이다. 범위를 넓히면 오탐이 된다."""
    assert "N24" not in codes(
        swap(
            "- 캐릭터 생성 화면의 외모 묘사는 한국어로 음성 출력되지 않습니다.",
            "- 캐릭터 생성 화면의 외모 묘사를 알려 줌.",
        )
    )


def test_N24_사용자가_고친_판은_안_걸린다():
    assert "N24" not in codes(USER_EDITED)


def test_N25_세_번째_표지_줄을_만들면_걸린다():
    """`v5.94.0.0`이 `한국어판 변경사항은 다음과 같습니다.`를 새로 만들었다."""
    assert "N25" in codes(
        swap(
            "- 설치 프로그램이 .NET 10 데스크톱 런타임을 자동으로 내려받아 설치하도록 함.",
            "한국어판 변경사항은 다음과 같습니다.\n\n"
            "- 설치 프로그램이 .NET 10 데스크톱 런타임을 자동으로 내려받아 설치하도록 함.",
        )
    )


def test_N25_두_표지는_통과한다():
    assert "N25" not in codes(
        swap(
            "- 설치 프로그램이 .NET 10 데스크톱 런타임을 자동으로 내려받아 설치하도록 함.",
            "한국어 번역 문장 수정:\n\n"
            "- 안내 열셋을 한국어로 옮김.\n\n"
            "모드 변경사항:\n\n"
            "- 설치 프로그램이 .NET 10 데스크톱 런타임을 자동으로 내려받아 설치하도록 함.",
        ).replace("\n모드 변경사항: 없음.\n", "\n")
    )


def test_N25_들여쓴_예시_줄은_통과한다():
    """복사해 넣을 경로가 항목 사이에 들여쓰기로 들어간다."""
    assert "N25" not in codes(
        swap(
            "- 설치 프로그램이 .NET 10 데스크톱 런타임을 자동으로 내려받아 설치하도록 함.",
            "- 나중에 직접 구한 파일을 아래 폴더에 넣을 수 있음.\n\n"
            r"  `%APPDATA%\XIVLauncherKR\pluginConfigs`"
            "\n\n"
            "- 설치 프로그램이 .NET 10 데스크톱 런타임을 자동으로 내려받아 설치하도록 함.",
        )
    )


def test_N25_마지막_항목_뒤의_꼬리는_안_본다():
    """`원본 모드의 전체 변경 이력은 …` 두 줄이 발행본마다 절 끝에 있다."""
    assert "N25" not in codes(
        swap(
            "모드 변경사항: 없음.",
            "모드 변경사항: 없음.\n\n원본 모드의 전체 변경 이력은 아래 주소에 있습니다.",
        )
    )


def test_N25_사용자가_고친_판은_안_걸린다():
    assert "N25" not in codes(USER_EDITED)


# ------------------------------------------------------------ 노트가 사는 곳
#
# **옛 저장소는 배포 폴더에 손으로 쓰고 그대로 올렸다.** 그 폴더가
# `.gitignore`에 있어서 본문이 판마다 사라졌다. 이 저장소는 `docs/release-notes/`가
# 그 자리이고, 파일 하나가 판 하나다.


def test_노트_디렉토리가_docs_아래에_있다():
    assert notes_check.NOTES_DIR == notes_check.REPO / "docs" / "release-notes"
    assert notes_check.NOTES_DIR.is_dir()


def test_판_번호가_아닌_이름은_노트가_아니다(tmp_path):
    (tmp_path / "5.94.0.0.md").write_text("x", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    assert [p.name for p in notes_check.note_paths(tmp_path)] == ["5.94.0.0.md"]
    assert notes_check.current_version(tmp_path) == "5.94.0.0"


def test_마디를_숫자로_견준다(tmp_path):
    # 글자로 견주면 `5.9`가 `5.10`보다 뒤로 간다.
    for name in ("5.9.0.0", "5.10.0.0"):
        (tmp_path / f"{name}.md").write_text("x", encoding="utf-8")
    assert notes_check.current_version(tmp_path) == "5.10.0.0"


def test_노트가_없으면_이번_판도_없다(tmp_path):
    assert notes_check.current_version(tmp_path) is None


def test_노트가_없으면_조용히_통과하지_않는다(tmp_path, monkeypatch, capsys):
    """**아직 안 쓴 것과 다 쓴 것이 화면에서 같아지면 안 된다.**

    `pack_check`와 `release_manifest`가 배포 폴더가 없을 때 하는 것과 같은
    결이다 - 무엇이 없어서 못 재는지를 말하고 실패한다.
    """
    monkeypatch.setattr(notes_check, "NOTES_DIR", tmp_path)
    assert notes_check.main([]) == 1
    err = capsys.readouterr().err
    assert "검사할 노트가 없다" in err
    assert "docs/release-notes/README.md" in err


def test_이번_판_노트를_인자_없이_찾는다(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(notes_check, "NOTES_DIR", tmp_path)
    (tmp_path / f"{VERSION}.md").write_text(USER_EDITED, encoding="utf-8")
    assert notes_check.main([]) == 0
    assert f"{VERSION}.md" in capsys.readouterr().out


def test_판_번호를_파일_이름에서_뽑는다(tmp_path, capsys):
    # 파일 하나가 판 하나라 이름이 곧 판 번호다. 손으로 주면 어긋날 자리가 생긴다.
    path = tmp_path / f"{VERSION}.md"
    path.write_text(USER_EDITED, encoding="utf-8")
    assert notes_check.main([str(path)]) == 0
    assert "통과" in capsys.readouterr().out


def test_이름이_판_번호가_아니면_버전을_요구한다(tmp_path):
    path = tmp_path / "메모.md"
    path.write_text(USER_EDITED, encoding="utf-8")
    with pytest.raises(SystemExit):
        notes_check.main([str(path)])


def test_노트_파일이_없으면_지목한다(tmp_path, capsys):
    assert notes_check.main([str(tmp_path / f"{VERSION}.md")]) == 1
    assert "릴리스 노트가 없다" in capsys.readouterr().err


# ------------------------------------------------------------ 커밋 훅이 쓸 자리
#
# **이 저장소에는 커밋 훅이 없다.** `.git/hooks`가 비어 있고 `core.hooksPath`도
# 안 걸려 있다. `--current-only`는 훅이 생기면 쓸 자리이고, 나가 있는 판을
# 소급해 고치지 않으므로 옛 판을 고치는 커밋이 여기서 막히면 안 된다.


def test_옛_판만_주면_건너뛴다(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(notes_check, "NOTES_DIR", tmp_path)
    old = tmp_path / "5.87.0.0.md"
    old.write_text("옛 판이다\n", encoding="utf-8")
    (tmp_path / f"{VERSION}.md").write_text(USER_EDITED, encoding="utf-8")

    assert notes_check.main(["--current-only", str(old)]) == 0
    assert "건너뜀" in capsys.readouterr().out


def test_이번_판이_섞여_있으면_그것을_본다(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(notes_check, "NOTES_DIR", tmp_path)
    old = tmp_path / "5.87.0.0.md"
    old.write_text("옛 판이다\n", encoding="utf-8")
    current = tmp_path / f"{VERSION}.md"
    current.write_text(USER_EDITED, encoding="utf-8")

    assert notes_check.main(["--current-only", str(old), str(current)]) == 0
    assert f"{VERSION}.md" in capsys.readouterr().out


def test_이번_판_지정과_버전_지정은_같이_못_쓴다():
    with pytest.raises(SystemExit):
        notes_check.main(["--current-only", "--version", "5.94.0.0"])


# ------------------------------------------------------------ N26

# 사용자가 두 번 지적한 자리다(2026-08-24 교정 둘). 절 이름이 주체와 조건을
# 이미 말하는데 줄마다 `원본 개발자가 ... 밝혔습니다`를 붙였고, 그것은 원문에
# 없는 어구를 지어내는 것이기도 하다. `v5.94.0.0`이 또 그렇게 나갔다.

_UNVERIFIED_LINE = (
    "- 장판 경고음은 기본으로 꺼져 있습니다. "
    "장판 모양 인식이 게임에서 아직 최종 확인되지 않았습니다"
)


def test_N26_지어낸_어구가_걸린다():
    # `v5.94.0.0`이 실제로 낸 문구다.
    assert "N26" in codes(
        swap(_UNVERIFIED_LINE, "- 딥 던전 기능을 원본 개발자가 게임에서 확인했다고 밝힘.")
    )


def test_N26_활용형을_같이_본다():
    for tail in ("밝힘", "밝혔음", "밝히고", "밝혀 둠"):
        assert "N26" in codes(swap(_UNVERIFIED_LINE, f"- 원본 개발자가 확인 못 했다고 {tail}.")), (
            tail
        )


def test_N26_사용자가_고친_판은_안_걸린다():
    assert "N26" not in codes(USER_EDITED)


def test_N26_정해진_종결은_통과한다():
    for tail in notes_check.UNVERIFIED_ENDINGS:
        assert "N26" not in codes(swap(_UNVERIFIED_LINE, f"- 장판 회피 방향이 맞는지 {tail}")), tail


def test_N26_부연으로_끝나는_줄은_통과한다():
    # **종결형을 둘로 좁히면 안 된다.** 발행본 열하나의 미검증 줄이
    # 부연으로 끝나고 그 전부가 정당하다.
    for line in (
        "- 장판 경고음은 기본으로 꺼져 있음. "
        "전투 중에 잘못된 경고음이 나는 것이 아예 없는 것보다 나쁨.",
        "- 딥 던전 기능을 게임에서 확인하지 못함. 설정에서 키를 바꿀 수 있음.",
        "- 새 안내는 게임에서 돌려 보지 못함. 길 정보 데이터를 대고 오프라인으로 검증함.",
    ):
        assert "N26" not in codes(swap(_UNVERIFIED_LINE, line)), line


def test_N26_변경사항_절은_안_본다():
    # 변경 항목에서 무엇을 발화하는지 인용하는 자리는 N24가 갖는다.
    assert "N26" not in codes(
        swap(
            "- 바탕화면 바로가기로 게임과 KR 달라무드 업데이터가 실행되도록 함.",
            "- 원본이 무엇을 고쳤는지 밝힌 대로 옮김.",
        )
    )


# ------------------------------------------------------------ 저장소의 노트


def test_저장소의_노트가_전부_규칙을_지킨다():
    """**나가 있는 판은 소급해 고치지 않는다.** 새 규칙이 옛 판을 빨갛게
    만들면 규칙 쪽이 너무 넓은 것이다."""
    paths = notes_check.note_paths()
    if not paths:
        pytest.skip("발행한 노트가 아직 없다 - 첫 판 노트는 다음 단계에서 쓴다")
    for path in paths:
        text, violations = notes_check.decode(path.read_bytes())
        violations += notes_check.check(text, path.stem)
        assert violations == [], (path.name, [str(v) for v in violations])
