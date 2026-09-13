"""번역의 구두점이 독일어 원문에서 벗어나는 것을 잡는지 잰다.

막는 사고는 2026-09-13에 실제로 나온 것이다. 대장 1,085행 중 **54행이 원문과
구두점이 달랐고** 아무 검사도 안 걸렸다. 목록 안내 13곳은 끝 마침표까지 버려서
음성 합성이 다음 발화와 붙었다.
"""

import ko_punct

# --- 부호를 어떻게 세나 ----------------------------------------------------


def test_보간_자리_안의_부호는_안_센다():
    """`{fullAngleDeg:0.#}`의 콜론과 마침표는 서식 지정자지 문장 부호가 아니다.

    안 지우면 오탐이 쏟아진다. 실측에서 물음표를 그렇게 세니 23건이 나왔는데
    실제로는 1건이었다 - C# 삼항의 `?`를 문장 부호로 본 것이다.
    """
    assert ko_punct.signature("각도 {fullAngleDeg:0.#}도.") == "."


def test_부호만_차례대로_뽑는다():
    assert ko_punct.signature("경유지: 3곳, 통로 1곳.") == ":,."


# --- 무엇을 결함으로 보나 --------------------------------------------------


def test_원문의_콜론을_버리면_걸린다():
    assert "콜론" in ko_punct.faults("Wegpunkte: {count} im Gebiet.", "경유지, {count}곳.")


def test_원문에_없는_콜론을_붙이면_걸린다():
    assert "콜론" in ko_punct.faults("Raus nach {d}, {m}.", "회피: {d}, {m}.")


def test_끝_마침표를_버리면_걸린다():
    """버리면 음성 합성이 거기서 안 쉬고 다음 발화와 붙는다."""
    assert "마침표" in ko_punct.faults("Wegpunkte: {count}.", "경유지: {count}곳")


def test_원문의_두_문장을_하나로_합치면_걸린다():
    de = "Enter öffnet das Hauptmenü. Strg+F1 sagt diese Hilfe erneut an."
    ko = "엔터는 주 메뉴 열기, 컨트롤 F1은 도움말 다시 듣기."
    assert "마침표" in ko_punct.faults(de, ko)


def test_물음표를_버리면_걸린다():
    assert "물음표·느낌표" in ko_punct.faults("Was soll darauf?", "무엇을 배정할지 선택.")


def test_느낌표를_버리면_걸린다():
    """스킬 §3이 느낌표를 금지하던 것을 2026-09-13에 물렸다. 원문에 있으면 옮긴다."""
    assert "물음표·느낌표" in ko_punct.faults("Biss!", "입질.")


def test_원문에_없는_쉼표를_붙이면_걸린다():
    assert "쉼표" in ko_punct.faults(
        "{enemy} wirkt {action} auf dich.", "{enemy}, 나에게 {action} 시전."
    )


def test_세미콜론이_다르면_걸린다():
    """지금 대장에 0건이라 잠든 갈래다. 생기는 날 이 줄이 이미 서 있다."""
    assert "세미콜론" in ko_punct.faults("A; B.", "가 나.")


# --- 무엇을 결함으로 안 보나 (독일어 고유 관습) ----------------------------


def test_절_앞_쉼표가_연결어미에_흡수되면_안_걸린다():
    """독일어 정서법이 종속절·등위절 앞에 쉼표를 강제한다. 한국어는 `~어서`가 그 일을 한다."""
    de = "Aktuelle Karte unbekannt, kann Koordinaten nicht bestimmen."
    assert ko_punct.faults(de, "현재 지도를 알 수 없어 좌표를 정할 수 없음.") == []


def test_원문_쉼표를_마침표로_가르면_안_걸린다():
    de = "Auto-Lauf abgebrochen, vnavmesh antwortet nicht."
    assert ko_punct.faults(de, "자동 이동 중단. vnavmesh가 응답하지 않음.") == []


def test_원문_줄표를_마침표로_가르면_안_걸린다():
    de = "{target} ist nicht erreichbar - dorthin führt kein Weg."
    assert ko_punct.faults(de, "{target}에 닿을 수 없음. 그리로 가는 길이 없음.") == []


def test_약어_마침표는_문장_끝으로_안_센다():
    """`Nr.`는 `Nummer`의 약어라 문장 경계가 아니다."""
    assert ko_punct.faults("{name}, Nr. {number}", "{name}, {number}번") == []


# --- 나열 접속사는 규칙이 아니라 판정 목록이 뺀다 --------------------------


def test_나열_접속사를_자동으로_면제하지_않는다():
    """`und`가 있으면 무조건 빼면 **등위절 `und`가 새어 나간다.**

    실측 사고가 그것이다. `{quest} ist in einem anderen Gebiet und ich finde
    keinen Übergang dorthin.`의 `und`는 나열이 아닌데 낱말만 보고 면제해서,
    원문에 없는 쉼표 하나가 검사를 통과했다. 검사기가 독일어 구문을 추측하는
    대신 **사람이 판정해 목록에 넣는다** - 이 저장소가 낱말과 문체에서 이미
    쓰는 방식이다.
    """
    de = "{quest} ist in einem anderen Gebiet und ich finde keinen Übergang dorthin."
    assert "쉼표" in ko_punct.faults(de, "{quest}, 다른 지역에 있고 통로를 찾을 수 없음.")


# --- 판정 목록의 위생 ------------------------------------------------------


def test_판정_목록이_있다():
    assert ko_punct.HELD_FILE.is_file(), f"{ko_punct.HELD_FILE}가 없다"


def test_판정_목록의_갈래가_둘뿐이다():
    for entry in ko_punct.load_held().values():
        assert entry["kind"] in ko_punct.KINDS, entry


def test_판정_목록에_사유와_날짜와_면제_갈래가_있다():
    """`why`가 비면 다음 사람이 그 줄을 근거 없이 믿는다."""
    for de, entry in ko_punct.load_held().items():
        assert entry["why"].strip(), f"{de}: why가 비었다"
        assert entry["when"].strip(), f"{de}: when이 비었다"
        assert entry["faults"], f"{de}: 무슨 갈래를 빼는지 안 적혀 있다"


def test_면제하지_않은_갈래는_계속_걸린다():
    """면제는 부호 갈래 단위다. 행을 통째로 빼면 그 줄의 다른 결함이 영영 안 보인다.

    실측 사고가 그것이다. 나열 쉼표로 뺀 행에 콜론 결함이 같이 있었는데,
    행 단위 면제라 검사가 그 행을 통째로 건너뛰었다.
    """
    rows = [{"de": "Sprache: a oder b.", "en": "", "ko": "언어 가, 나."}]
    held = {"Sprache: a oder b.": {"kind": "나열", "faults": ["쉼표"], "why": "x", "when": "y"}}
    problems = ko_punct.check_strings(rows=rows, held=held)
    assert any("콜론" in p for p in problems), problems


def test_대장에_없는_행을_면제하면_걸린다():
    """번역이 바뀌었는데 면제가 남으면 아무도 못 본다."""
    held = {"없는 원문": {"kind": "나열", "faults": ["쉼표"], "why": "x", "when": "y"}}
    assert any("대장에 없다" in p for p in ko_punct.check_held(rows=[], held=held))


def test_어긋나지_않는_행을_면제하면_걸린다():
    """고쳐 놓고 면제를 안 지우면 목록이 쓰레기를 모은다."""
    rows = [{"de": "Ziel {name}.", "en": "", "ko": "대상 {name}."}]
    held = {"Ziel {name}.": {"kind": "보류", "faults": ["쉼표"], "why": "x", "when": "y"}}
    assert any("안 걸린다" in p for p in ko_punct.check_held(rows=rows, held=held))


def test_모르는_갈래를_면제하면_걸린다():
    rows = [{"de": "Ziel {name}.", "en": "", "ko": "대상 {name}, 찾음."}]
    held = {"Ziel {name}.": {"kind": "보류", "faults": ["물결표"], "why": "x", "when": "y"}}
    assert any("물결표" in p for p in ko_punct.check_held(rows=rows, held=held))


# --- 실제 대장 - 이것이 회귀 방지다 ----------------------------------------


def test_대장이_통과한다():
    """판정 목록으로 뺀 것 말고는 어긋난 행이 없어야 한다."""
    problems = ko_punct.check_strings()
    assert problems == [], "\n".join(problems)


def test_판정_목록이_대장과_맞는다():
    assert ko_punct.check_held() == []


def test_보류가_다섯건_이하다():
    """보류는 사용자 판정을 기다리는 빚이다. 늘어나면 이 줄이 먼저 빨개진다.

    2026-09-13 기준 다섯이고, 전부 쉼표를 지우면 말이 붙거나 어미까지
    건드려야 하는 자리다.
    """
    held = ko_punct.load_held()
    pending = [de for de, e in held.items() if e["kind"] == "보류"]
    assert len(pending) <= 5, f"보류가 {len(pending)}건이다: {pending}"


def test_main이_통과하면_0으로_끝난다():
    assert ko_punct.main([]) == 0


# --- 휴면 경로 - 세션 중에는 안 도는 갈래를 인위로 밟는다 -------------------


def test_어긋난_행이_있으면_1로_끝난다(monkeypatch, capsys):
    """실패 갈래는 대장이 깨끗한 동안 영영 안 돈다. 배선만 보고 넘기지 않는다."""
    broken = [{"de": "Wegpunkte: {count}.", "en": "", "ko": "경유지, {count}곳"}]
    monkeypatch.setattr(ko_punct, "load_rows", lambda *a, **k: broken)
    monkeypatch.setattr(ko_punct, "load_held", lambda *a, **k: {})

    assert ko_punct.main([]) == 1
    assert "콜론" in capsys.readouterr().err


def test_보류가_상한을_넘으면_걸린다():
    """보류는 빚이라 늘면 먼저 빨개진다. 상한은 판정 당시 건수로 잡았다."""
    rows = [
        {"de": f"Ziel {i} gefunden.", "en": "", "ko": f"대상 {i}, 찾음."}
        for i in range(ko_punct.PENDING_LIMIT + 1)
    ]
    held = {
        row["de"]: {
            "kind": "보류",
            "faults": ["쉼표"],
            "why": "쉼표를 지우면 붙는다",
            "when": "2026-09-13",
        }
        for row in rows
    }
    problems = ko_punct.check_held(rows=rows, held=held)
    assert any("상한" in p for p in problems), problems
