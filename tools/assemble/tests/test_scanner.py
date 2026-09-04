"""소스에서 문장 자리를 읽고 다시 쓰는 부분의 검사."""

from __future__ import annotations

import scanner


def test_주석은_같은_길이의_공백이_된다() -> None:
    """길이가 그대로여야 위치가 원문과 1대1로 맞는다."""
    text = 'var a = 1; // IsGerman ? "x" : "y"\nvar b = 2;\n'
    stripped = scanner.strip_comments(text)

    assert len(stripped) == len(text)
    assert "IsGerman" not in stripped
    assert stripped.startswith("var a = 1; ")
    assert stripped.endswith("var b = 2;\n")


def test_문자열_안의_슬래시_둘은_주석이_아니다() -> None:
    text = 'var url = "https://example.com"; // 진짜 주석\n'
    stripped = scanner.strip_comments(text)

    assert "https://example.com" in stripped
    assert "진짜 주석" not in stripped


def test_블록_주석도_지운다() -> None:
    text = "a /* IsGerman ? 1 : 2 */ b\n"
    stripped = scanner.strip_comments(text)

    assert len(stripped) == len(text)
    assert stripped == "a" + " " * 23 + " b\n"


def test_축자_문자열은_읽지_않는다() -> None:
    """`@"..."`는 이스케이프 규칙이 달라서 손대지 않는다."""
    text = '@"C:\\path"'
    value, _, _ = scanner.read_literal(text, 1)

    assert value is None


def test_보간_접두를_포함해_리터럴을_읽는다() -> None:
    text = 'x = $"{name} 준비";'
    value, start, end = scanner.read_literal(text, 4)

    assert value == "{name} 준비"
    assert text[start:end] == '$"{name} 준비"'


def test_삼항_자리를_찾는다() -> None:
    text = 'public static string A => IsGerman ? "Hallo" : "Hello";\n'
    sites = scanner.find_sites(text)

    assert len(sites) == 1
    assert (sites[0].de, sites[0].en) == ("Hallo", "Hello")
    assert sites[0].ko is None
    assert sites[0].qualifier == ""


def test_Loc_표기를_그대로_되쓴다() -> None:
    """파일마다 관례가 다르다. 한쪽으로 통일하면 안 쓰던 표기가 섞인다."""
    text = 'var s = Loc.IsGerman ? "Hallo" : "Hello";\n'
    sites = scanner.find_sites(text)

    assert sites[0].qualifier == "Loc."
    assert text[sites[0].start :].startswith("Loc.IsGerman")


def test_이미_옮긴_Pick도_자리로_잡힌다() -> None:
    text = 'public static string A => Pick("Hallo", "Hello", "안녕");\n'
    sites = scanner.find_sites(text)

    assert len(sites) == 1
    assert sites[0].ko == "안녕"


def test_다른_이름의_Pick은_거른다() -> None:
    text = 'var x = PickItem("Hallo", "Hello");\n'

    assert scanner.find_sites(text) == []


def test_대장에_있는_쌍에만_한국어가_들어간다() -> None:
    text = (
        'public static string A => IsGerman ? "Hallo" : "Hello";\n'
        'public static string B => IsGerman ? "Tschuess" : "Bye";\n'
    )
    result = scanner.rewrite(text, {("Hallo", "Hello"): "안녕"})

    assert 'Pick("Hallo", "Hello", "안녕")' in result.text
    assert result.applied == [("Hallo", "Hello")]
    assert result.seen == [("Hallo", "Hello"), ("Tschuess", "Bye")]


def test_대장에_없는_삼항도_인자_둘짜리_Pick이_된다() -> None:
    """그래야 한국어 모드에서 Loc.Pick을 타고, 그 자리가 로그에 남는다.

    삼항을 그대로 두면 모드가 자기가 영어를 낸 것을 모른다. 보이지 않는 사용자는
    "아직 번역 안 됨"과 "모드가 죽음"을 못 가르는데, 조립 보고는 그 사람에게 안 보인다.
    """
    text = 'public static string B => IsGerman ? "Tschuess" : "Bye";\n'
    result = scanner.rewrite(text, {})

    assert result.text == 'public static string B => Pick("Tschuess", "Bye");\n'
    assert result.applied == []


def test_독일어와_영어는_한_자도_안_바뀐다() -> None:
    """인자 둘짜리로 바뀌어도 두 언어가 듣는 것은 그대로여야 한다."""
    text = 'var x = Loc.IsGerman ? $"Hallo {n}" : "Bye";\n'
    result = scanner.rewrite(text, {})

    assert result.text == 'var x = Loc.Pick($"Hallo {n}", "Bye");\n'


def test_보간_자리가_있으면_한국어에_달러를_붙인다() -> None:
    text = 'public static string A(string item) => IsGerman ? $"Hallo {item}" : $"Hi {item}";\n'
    result = scanner.rewrite(text, {("Hallo {item}", "Hi {item}"): "{item} 안녕"})

    assert '$"{item} 안녕"' in result.text


def test_보간_자리가_안_맞으면_한국어를_안_넣고_보고한다() -> None:
    """휴면 경로. 대장을 잘못 적으면 컴파일이 깨지거나 엉뚱한 값이 나간다."""
    text = 'public static string A(string item) => IsGerman ? $"Hallo {item}" : $"Hi {item}";\n'
    result = scanner.rewrite(text, {("Hallo {item}", "Hi {item}"): "{name} 안녕"})

    assert "안녕" not in result.text
    assert 'Pick($"Hallo {item}", $"Hi {item}")' in result.text
    assert result.applied == []
    assert len(result.bad_slots) == 1
    assert "보간 자리" in result.bad_slots[0]


def test_못_읽은_갈림길을_행_번호로_센다() -> None:
    """중첩 삼항은 이 파서의 손 밖이다. 못 읽으면 못 세므로 개수라도 낸다."""
    text = (
        'public static string A => IsGerman ? "Hallo" : "Hello";\n'
        'public static string B => IsGerman ? $"{(on ? "an" : "aus")}" : "off";\n'
    )
    sites, unreadable = scanner.scan(text)

    assert [(site.de, site.en) for site in sites] == [("Hallo", "Hello")]
    assert unreadable == [2]


def test_못_읽은_자리는_손대지_않는다() -> None:
    text = 'public static string B => IsGerman ? Concat(a, b) : "off";\n'
    result = scanner.rewrite(text, {})

    assert result.text == text
    assert result.unreadable == [1]


def test_긴_호출은_여는_괄호에_맞춰_줄을_나눈다() -> None:
    de = "Ein sehr langer deutscher Satz, der die Zeile weit ueber hundert Spalten hinaus traegt."
    text = f'    public static string A => IsGerman ? "{de}" : "A very long English sentence.";\n'
    result = scanner.rewrite(text, {(de, "A very long English sentence."): "아주 긴 한국어 문장."})

    lines = result.text.split("\n")
    pad = " " * (len("    public static string A => ") + len("Pick("))
    assert len(lines) == 4  # 인자 셋 + 끝의 빈 줄
    assert lines[0].endswith(f'"{de}",')
    assert lines[1] == f'{pad}"A very long English sentence.",'
    assert lines[2] == f'{pad}"아주 긴 한국어 문장.");'


def test_이미_같은_한국어가_박혀_있으면_손대지_않는다() -> None:
    text = 'public static string A => Pick("Hallo", "Hello", "안녕");\n'
    result = scanner.rewrite(text, {("Hallo", "Hello"): "안녕"})

    assert result.text == text
    assert result.applied == []


def test_호출부_이름을_찾는다() -> None:
    """`[CallerMemberName]`이 런타임에 넘기는 이름과 같은 것을 정적으로 뽑는다."""
    text = (
        "public static partial class S\n"
        "{\n"
        '    public static string TitleScreen => IsGerman ? "Titel" : "Title";\n'
        '    public static string Confirmed(string item) => IsGerman ? "Ja" : "Yes";\n'
        "}\n"
    )
    sites = scanner.find_sites(text)

    assert [scanner.member_name(text, site.start) for site in sites] == [
        "TitleScreen",
        "Confirmed",
    ]


def test_이름을_못_찾으면_빈_문자열이다() -> None:
    text = 'var x = IsGerman ? "Ja" : "Yes";\n'
    site = scanner.find_sites(text)[0]

    assert scanner.member_name(text, site.start) == ""
