"""게임 용어 대장 검사.

이 대장이 막는 사고는 하나고, 이 저장소는 그걸 이미 한 번 겪었다 - 그럴듯한
용어를 지어내 결정으로 박아 두는 것. `Aetheryte`를 "에테라이트"라고 스킬에
적어 놨었는데 그때는 확인한 적이 없었다(지금은 확인됐다, Addon 2723행).

그래서 모든 줄이 **시트와 행 번호와 그 행의 원문**을 함께 갖는다. 구조 검사는
늘 돌고, 게임 데이터와의 대조는 덤프가 있을 때만 돈다.
"""

import json

import pytest
import terms

CATALOG = terms.CATALOG


@pytest.fixture(scope="module")
def catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


# --- 구조 - 늘 돈다 --------------------------------------------------------


def test_대장이_있다():
    assert CATALOG.is_file(), f"{CATALOG}가 없다"


def test_줄마다_행_번호가_있다(catalog):
    # 번호 없는 줄은 "어디서 봤는지 모르는 용어"다. 그게 지어낸 것과 구분이 안 된다.
    # 시트도 같이 봐야 한다 - 행 번호만으로는 어느 시트의 27행인지 모른다.
    for row in catalog["terms"]:
        sheet, number = terms.source_of(row)
        assert sheet in terms.SHEETS, row
        assert isinstance(number, int), row
        assert number > 0, row


def _why_row_is_wrong(row: dict) -> str | None:
    """대장 한 줄이 자기 안에서 앞뒤가 맞는지. 맞으면 None, 아니면 까닭.

    보통은 한국어가 그 행의 원문 안에 통째로 있어야 한다. 예외는 **시트의
    낱말에 일반 명사를 붙여 만든 말**이고, 그런 줄은 `composed_from`에 재료를
    적는다. 그때는 재료가 시트에 있는지를 대신 재므로, 지어낸 말은 재료부터
    걸려서 이 필드가 면죄부가 되지 않는다.
    """
    stem = row.get("composed_from")
    if stem is None:
        if row["ko"] not in row["row_text"]:
            return "한국어가 그 행의 원문에 없다"
        return None
    if stem not in row["row_text"]:
        return "조합의 재료가 그 행의 원문에 없다"
    if stem not in row["ko"]:
        return "한국어가 적어 둔 재료를 품고 있지 않다"
    if row["ko"] == stem:
        return "붙인 말이 없으니 조합이 아니다 - composed_from을 지워라"
    return None


def test_한국어가_원문_안에_있다(catalog):
    # 대장이 자기 안에서 먼저 앞뒤가 맞아야 한다.
    for row in catalog["terms"]:
        assert _why_row_is_wrong(row) is None, (_why_row_is_wrong(row), row)


def test_조합어_예외가_지어낸_말을_통과시키지_않는다():
    # composed_from을 달았다고 넘어가면 이 검사가 있으나 마나다.
    행 = "채집 관련 시스템 메시지"
    지어냄 = {"ko": "에테라이트 광장", "row_text": 행, "composed_from": "에테라이트"}
    assert _why_row_is_wrong(지어냄) is not None, "재료가 시트에 없는데 통과했다"

    안_붙임 = {"ko": "채집", "row_text": 행, "composed_from": "채집"}
    assert _why_row_is_wrong(안_붙임) is not None, "조합이 아닌데 통과했다"

    딴_재료 = {"ko": "제작 지점", "row_text": 행, "composed_from": "채집"}
    assert _why_row_is_wrong(딴_재료) is not None, "재료를 안 품었는데 통과했다"

    제대로 = {"ko": "채집 지점", "row_text": 행, "composed_from": "채집"}
    assert _why_row_is_wrong(제대로) is None


def test_영어가_겹치지_않는다(catalog):
    names = [row["en"] for row in catalog["terms"]]
    assert len(names) == len(set(names)), "같은 영어에 두 답이 있으면 어느 쪽인지 모른다"


def test_못_찾은_것을_지우지_않는다(catalog):
    # 없다는 것도 결과다. 특히 이것 - 게임은 "채팅"을 안 쓴다.
    assert "채팅" in catalog["not_found"]


def test_게임_판번호를_적어_뒀다(catalog):
    # 게임이 올라가면 용어가 바뀔 수 있다. 언제 뽑았는지 없으면 못 되짚는다.
    assert catalog["game_version"]
    assert catalog["dumped"]


# --- 게임 데이터와 대조 - 덤프가 있을 때만 --------------------------------


def _referenced_sheets(catalog: dict) -> set[str]:
    return {terms.source_of(row)[0] for row in catalog["terms"]}


def _require_dumps(sheets: set[str]) -> None:
    missing = sorted(s for s in sheets if not terms.dump_path(s).is_file())
    if missing:
        pytest.skip(
            f"덤프가 없는 시트: {', '.join(missing)} - "
            f"dotnet run --project tools/ko-terms/koterms.csproj -c Release "
            f"-- dump tools/ko-terms/out --sheet all"
        )


def test_행마다_게임이_같은_말을_한다(catalog):
    # 게임이 올라가면서 낱말을 바꾸면 여기가 빨개진다. 대장이 가리키는 시트를
    # 전부 요구한다 - 한 시트만 뽑아 두고 나머지를 조용히 건너뛰면 대조가 반만
    # 돌면서 다 돈 것처럼 보인다.
    needed = _referenced_sheets(catalog)
    _require_dumps(needed)

    dumps = {sheet: terms.load_dump(sheet) for sheet in needed}
    missing = []
    changed = []
    for row in catalog["terms"]:
        sheet, number = terms.source_of(row)
        text = dumps[sheet].get(number)
        if text is None:
            missing.append(row)
        elif text != row["row_text"]:
            changed.append((row, text))

    assert not missing, f"게임 데이터에 없는 행: {missing}"
    assert not changed, f"게임이 다른 말을 한다: {changed}"


def test_못_찾았다고_적은_낱말이_정말_없다(catalog):
    # `not_found`가 주장하는 것은 **Addon 시트에 없다**는 것이고, 줄마다 붙은
    # 설명도 그 범위로 적혀 있다. 여기서 시트를 넓히면 검사가 설명보다 넓은
    # 것을 주장하게 된다 - 실제로 `장판`은 Action 시트에 7행 있다(다른 뜻의
    # 보스 기술 이름이다). 넓힐 거라면 줄마다 어느 시트를 뒤졌는지부터 적어야
    # 한다.
    _require_dumps({terms.DEFAULT_SHEET})

    rows = terms.load_dump()
    for word in catalog["not_found"]:
        hits = [n for n, text in rows.items() if word in text]
        assert not hits, f"'{word}'는 없다고 적었는데 {len(hits)}행에 있다: {hits[:5]}"
