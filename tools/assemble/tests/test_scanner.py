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


def test_보간_자리_안의_따옴표는_리터럴의_끝이_아니다() -> None:
    """보간 자리 안은 식이라 그 안의 문자열이 escape 없이 그대로 들어간다."""
    text = 'x = $"{name}, {(on ? "an" : "aus")}";'
    value, start, end = scanner.read_literal(text, 4)

    assert value == '{name}, {(on ? "an" : "aus")}'
    assert text[start:end] == '$"{name}, {(on ? "an" : "aus")}"'


def test_보간_자리_안의_보간_리터럴도_읽는다() -> None:
    """안쪽이 또 보간이면 안쪽에서도 깊이를 세야 3중 중첩이 안 깨진다."""
    text = 'x = $"{a}{(b ? "x" : $"{c} P")}";'
    value, start, end = scanner.read_literal(text, 4)

    assert value == '{a}{(b ? "x" : $"{c} P")}'
    assert text[start:end] == '$"{a}{(b ? "x" : $"{c} P")}"'


def test_달러가_없으면_중괄호를_세지_않는다() -> None:
    """보간이 아닌 리터럴에서 깊이를 세면 짝 없는 `{` 하나가 닫는 따옴표를 삼킨다."""
    text = 'x = "{ 짝이 없는 중괄호"; var y = 1;'
    value, start, end = scanner.read_literal(text, 4)

    assert value == "{ 짝이 없는 중괄호"
    assert text[start:end] == '"{ 짝이 없는 중괄호"'


def test_중괄호_둘은_자리가_아니라_글자다() -> None:
    """`{{`를 자리로 세면 깊이가 안 맞아 리터럴이 제자리에서 안 끝난다."""
    text = 'x = $"{{ {name}"; var y = 1;'
    value, start, end = scanner.read_literal(text, 4)

    assert value == "{{ {name}"
    assert text[start:end] == '$"{{ {name}"'


def test_중첩_안이_못_읽는_모양이면_바깥도_실패한다() -> None:
    """휴면 경로. 안쪽이 닫히기 전에 개행이 오면 바깥도 읽은 것으로 치면 안 된다."""
    text = 'x = $"{(on ? "an\n" : "aus")}";'
    value, _, _ = scanner.read_literal(text, 4)

    assert value is None


def test_보간_자리에_삼항이_있는_실제_모양을_자리로_잡는다() -> None:
    """`AccessibilityStrings.Chat.cs`의 `OptionToggle`이 이 모양이다."""
    text = (
        "    public static string OptionToggle(string name, bool on) =>\n"
        '        IsGerman ? $"{name}, {(on ? "an" : "aus")}" : $"{name}, {(on ? "on" : "off")}";\n'
    )
    sites = scanner.find_sites(text)

    assert len(sites) == 1
    assert sites[0].de == '{name}, {(on ? "an" : "aus")}'
    assert sites[0].en == '{name}, {(on ? "on" : "off")}'
    assert sites[0].de_raw == '$"{name}, {(on ? "an" : "aus")}"'
    assert sites[0].en_raw == '$"{name}, {(on ? "on" : "off")}"'


def test_중첩된_자리도_통째로_하나로_읽는다() -> None:
    """정규식은 안쪽 `{location}`만 잡고 바깥 자리를 통째로 놓친다."""
    text = '{name}{(location != null ? $", on {location}" : "")}'

    assert scanner.holes(text) == ["name", '(location != null ? $", on {location}" : "")']


def test_자리를_셀_때_중괄호_둘은_글자다() -> None:
    text = "{{ {name} }}"

    assert scanner.holes(text) == ["name"]


def test_자리_안의_따옴표_속_중괄호는_깊이를_안_흔든다() -> None:
    """자리 안의 문자열은 통째로 건너뛴다. 안 그러면 그 안의 `}`가 자리를 일찍 닫는다."""
    text = '{(on ? "}" : "{")}'

    assert scanner.holes(text) == ['(on ? "}" : "{")']


def test_자리의_순서를_바꾸는_것은_통과한다() -> None:
    """한국어는 어순이 달라서 자리를 그대로 두면 말이 안 된다."""
    ko = "{count}개 중 {index}번째"

    assert scanner.references("{index} of {count}") == scanner.references(ko)


def test_서식_지정자가_바뀌면_다른_자리다() -> None:
    """`{distance:F0}`를 `{distance}`로 적으면 소수 자릿수가 달라진 채로 나간다."""
    assert scanner.references("{distance:F0}") != scanner.references("{distance}")


def test_자리_안의_문장을_옮겨도_같은_자리다() -> None:
    """자리 안의 문장도 사용자가 듣는 말이라 번역 대상이다. 리터럴을 걷어내고 견준다."""
    assert scanner.references('{(on ? "on" : "off")}') == scanner.references('{(on ? "켬" : "끔")}')


def test_자리_안의_식이_바뀌면_다른_자리다() -> None:
    ko = '{(off ? "켬" : "끔")}'

    assert scanner.references('{(on ? "on" : "off")}') != scanner.references(ko)


def test_멀쩡한_값에는_까닭이_없다() -> None:
    assert scanner.body_fault('{name}, {(on ? "켬" : "끔")}') is None
    assert scanner.body_fault("중괄호 둘 {{ 은 글자다") is None


def test_중괄호_짝이_안_맞으면_까닭을_돌려준다() -> None:
    """C#이 컴파일을 거부한다. 대장은 사람이 손으로 고치는 파일이라 여기서 막는다."""
    assert scanner.body_fault("{name 준비됨") is not None
    assert scanner.body_fault("name} 준비됨") is not None


def test_자리_안에서_따옴표가_안_닫히면_까닭을_돌려준다() -> None:
    """안 닫힌 따옴표는 뒤따르는 코드를 통째로 문자열로 만든다."""
    assert scanner.body_fault('{(on ? "켬 : "끔")}') is not None


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
    assert "item" in result.bad_slots[0]
    assert "name" in result.bad_slots[0]


def test_자리의_순서를_바꾼_한국어가_들어간다() -> None:
    """`{index} of {count}`를 한국어 어순으로 옮기면 자리의 순서가 뒤집힌다."""
    text = "    public static string A(int index, int count) =>\n"
    text += '        IsGerman ? $"{index} von {count}" : $"{index} of {count}";\n'
    result = scanner.rewrite(
        text, {("{index} von {count}", "{index} of {count}"): "{count}개 중 {index}번째"}
    )

    assert '$"{count}개 중 {index}번째"' in result.text
    assert result.bad_slots == []


def test_서식_지정자를_뺀_한국어는_안_들어간다() -> None:
    """`{distance:F0}`를 `{distance}`로 적으면 소수 자릿수가 달라진 채로 나간다."""
    text = 'var s = IsGerman ? $"{d:F0} m" : $"{d:F0} m";\n'
    result = scanner.rewrite(text, {("{d:F0} m", "{d:F0} m"): "{d}미터"})

    assert "미터" not in result.text
    assert len(result.bad_slots) == 1


def test_자리_안의_문장을_옮긴_한국어가_들어간다() -> None:
    """이 모양이 이번에 열린 24곳이다. 자리 안은 식이라 따옴표가 escape 없이 들어간다."""
    text = '    var s = IsGerman ? $"{n}, {(on ? "an" : "aus")}" : $"{n}, {(on ? "on" : "off")}";\n'
    result = scanner.rewrite(
        text,
        {('{n}, {(on ? "an" : "aus")}', '{n}, {(on ? "on" : "off")}'): '{n}, {(on ? "켬" : "끔")}'},
    )

    assert '$"{n}, {(on ? "켬" : "끔")}"' in result.text
    assert result.bad_slots == []


def test_못_읽은_갈림길을_행_번호로_센다() -> None:
    """중첩 삼항은 이 파서의 손 밖이다. 못 읽으면 못 세므로 개수라도 낸다."""
    text = (
        'public static string A => IsGerman ? "Hallo" : "Hello";\n'
        'public static string B => IsGerman ? (on ? "an" : "aus") : "off";\n'
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
