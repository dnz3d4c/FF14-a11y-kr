"""조립 절차 전체의 검사.

작은 가짜 저장소를 만들어 돌린다. 실제 원본으로 돌리는 검사는 여기 두지 않는다 -
서브모듈이 채워져 있어야 하고, 그건 이 검사들이 답해야 할 질문이 아니다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import assemble

PLUGIN = """namespace X;

public class Plugin
{
    private static bool IsGerman => Loc.IsGerman;

    public static string Hello => IsGerman ? "Hallo" : "Hello";
    public static string Bye => IsGerman ? "Tschuess" : "Bye";
    public static string Same => IsGerman ? "Ok" : "Ok";
}
"""

CATALOG = {
    "strings": [
        {"de": "Hallo", "en": "Hello", "ko": "안녕"},
        {"de": "Tschuess", "en": "Bye", "ko": "잘 가"},
    ]
}

RULES = {
    "rules": [
        {
            "name": "한국어-축약",
            "file": "FF14Accessibility/Plugin.cs",
            "why": "클래스 하나에 한 번만 선언한다.",
            "find": "    private static bool IsGerman => Loc.IsGerman;\n",
            "replace": (
                "    private static bool IsGerman => Loc.IsGerman;\n"
                "    private static string Pick(string de, string en, string? ko = null) =>\n"
                "        Loc.Pick(de, en, ko);\n"
            ),
        }
    ]
}


def _repo(tmp_path: Path, *, catalog: Mapping[str, object] | None = None) -> Path:
    repo = tmp_path / "repo"
    source = repo / "upstream" / "FF14Accessibility"
    source.mkdir(parents=True)
    (source / "Plugin.cs").write_text(PLUGIN, encoding="utf-8")
    (repo / "upstream" / "LICENSE").write_text("license\n", encoding="utf-8")

    (repo / "korean").mkdir()
    (repo / "korean" / "strings.json").write_text(
        json.dumps(catalog or CATALOG, ensure_ascii=False), encoding="utf-8"
    )

    (repo / "kr" / "FF14Accessibility").mkdir(parents=True)
    (repo / "kr" / "FF14Accessibility" / "Compat.cs").write_text("// 신규\n", encoding="utf-8")

    (repo / "replace").mkdir()
    (repo / "graft").mkdir()
    (repo / "graft" / "rules.json").write_text(
        json.dumps(RULES, ensure_ascii=False), encoding="utf-8"
    )
    return repo


def _built(repo: Path) -> str:
    return (repo / "build" / "FF14Accessibility" / "Plugin.cs").read_text(encoding="utf-8")


def test_조립이_한_번에_돈다(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report = assemble.assemble(repo)

    assert report.problems == []
    assert 'Pick("Hallo", "Hello", "안녕")' in _built(repo)
    assert 'Pick("Tschuess", "Bye", "잘 가")' in _built(repo)
    assert "private static string Pick(string de" in _built(repo)
    assert (repo / "build" / "FF14Accessibility" / "Compat.cs").read_text(
        encoding="utf-8"
    ) == "// 신규\n"
    assert (repo / "build" / "LICENSE").is_file()


def test_원본은_한_자도_안_바뀐다(tmp_path: Path) -> None:
    """조립은 build 안에서만 일어난다. 이 저장소의 전제다."""
    repo = _repo(tmp_path)
    assemble.assemble(repo)

    assert (repo / "upstream" / "FF14Accessibility" / "Plugin.cs").read_text(
        encoding="utf-8"
    ) == PLUGIN


def test_대장에_없는_자리에는_한국어가_안_들어간다(tmp_path: Path) -> None:
    """자리는 Pick으로 바뀌되 인자는 둘이다. 그래야 그 자리가 실행 중에 로그로 나온다."""
    repo = _repo(tmp_path)
    assemble.assemble(repo)

    assert 'Pick("Ok", "Ok");' in _built(repo)


def test_기존_build를_지우고_새로_만든다(tmp_path: Path) -> None:
    """지난 판의 찌꺼기가 남으면 무엇을 빌드했는지 알 수 없다."""
    repo = _repo(tmp_path)
    stale = repo / "build" / "찌꺼기.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("지난 판\n", encoding="utf-8")

    assemble.assemble(repo)

    assert not stale.exists()


def test_보고를_파일로도_낸다(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assemble.assemble(repo)

    saved = json.loads((repo / "build" / "assemble-report.json").read_text(encoding="utf-8"))
    assert saved["ok"] is True
    assert saved["applied_sites"] == 2
    assert saved["catalog_rows"] == 2


def test_미적용_자리를_이름과_함께_센다(tmp_path: Path) -> None:
    """판정 대상은 잔량이다. 영어로 나갈 자리가 어디인지를 본다."""
    repo = _repo(tmp_path)
    report = assemble.assemble(repo)

    assert [(site.name, site.en) for site in report.untranslated] == [("Same", "Ok")]


def test_고아를_센다(tmp_path: Path) -> None:
    """대장에는 있는데 소스에서 못 만난 쌍. 업스트림이 그 문장을 고쳤다는 신호다."""
    catalog = {"strings": [*CATALOG["strings"], {"de": "Weg", "en": "Gone", "ko": "사라짐"}]}
    repo = _repo(tmp_path, catalog=catalog)
    report = assemble.assemble(repo)

    assert report.orphans == [("Weg", "Gone")]
    assert report.problems == []


def test_kr의_파일이_원본에_이미_있으면_실패한다(tmp_path: Path) -> None:
    """그건 replace에 있어야 할 것이다."""
    repo = _repo(tmp_path)
    (repo / "kr" / "FF14Accessibility" / "Plugin.cs").write_text("// 겹침\n", encoding="utf-8")

    report = assemble.assemble(repo)

    assert len(report.problems) == 1
    assert "FF14Accessibility/Plugin.cs" in report.problems[0]
    assert "replace" in report.problems[0]


def test_replace의_파일이_원본에_없으면_실패한다(tmp_path: Path) -> None:
    """그건 kr에 있어야 할 것이다."""
    repo = _repo(tmp_path)
    (repo / "replace" / "FF14Accessibility").mkdir(parents=True)
    (repo / "replace" / "FF14Accessibility" / "Nowhere.cs").write_text(
        "// 없음\n", encoding="utf-8"
    )

    report = assemble.assemble(repo)

    assert len(report.problems) == 1
    assert "FF14Accessibility/Nowhere.cs" in report.problems[0]
    assert "kr" in report.problems[0]


def test_replace는_원본을_덮어쓴다(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "replace" / "FF14Accessibility").mkdir(parents=True)
    (repo / "replace" / "FF14Accessibility" / "Plugin.cs").write_text(
        "// 우리 것\n", encoding="utf-8"
    )
    (repo / "graft" / "rules.json").write_text(
        json.dumps({"rules": []}, ensure_ascii=False), encoding="utf-8"
    )

    report = assemble.assemble(repo)

    assert report.problems == []
    assert _built(repo) == "// 우리 것\n"


def test_replace의_원본이_바뀌면_경고한다(tmp_path: Path) -> None:
    """우리 사본이 낡았을 수 있다. 원본의 개선을 조용히 덮어쓰는 것이 이 부류의 위험이다."""
    repo = _repo(tmp_path)
    (repo / "replace" / "FF14Accessibility").mkdir(parents=True)
    (repo / "replace" / "FF14Accessibility" / "Plugin.cs").write_text(
        "// 우리 것\n", encoding="utf-8"
    )
    (repo / "replace" / "upstream-baseline.json").write_text(
        json.dumps({"files": {"FF14Accessibility/Plugin.cs": "0" * 64}}), encoding="utf-8"
    )
    (repo / "graft" / "rules.json").write_text(
        json.dumps({"rules": []}, ensure_ascii=False), encoding="utf-8"
    )

    report = assemble.assemble(repo)

    assert report.problems == []
    assert len(report.warnings) == 1
    assert "FF14Accessibility/Plugin.cs" in report.warnings[0]


def test_기준선이_맞으면_조용하다(tmp_path: Path) -> None:
    import hashlib

    repo = _repo(tmp_path)
    (repo / "replace" / "FF14Accessibility").mkdir(parents=True)
    (repo / "replace" / "FF14Accessibility" / "Plugin.cs").write_text(
        "// 우리 것\n", encoding="utf-8"
    )
    digest = hashlib.sha256(
        (repo / "upstream" / "FF14Accessibility" / "Plugin.cs").read_bytes()
    ).hexdigest()
    (repo / "replace" / "upstream-baseline.json").write_text(
        json.dumps({"files": {"FF14Accessibility/Plugin.cs": digest}}), encoding="utf-8"
    )
    (repo / "graft" / "rules.json").write_text(
        json.dumps({"rules": []}, ensure_ascii=False), encoding="utf-8"
    )

    assert assemble.assemble(repo).warnings == []


def test_대장의_한국어가_비면_실패한다(tmp_path: Path) -> None:
    catalog = {"strings": [{"de": "Hallo", "en": "Hello", "ko": "  "}]}
    repo = _repo(tmp_path, catalog=catalog)

    report = assemble.assemble(repo)

    assert len(report.problems) == 1
    assert "비어" in report.problems[0]


def test_대장에_같은_쌍이_중복이면_실패한다(tmp_path: Path) -> None:
    catalog = {
        "strings": [
            {"de": "Hallo", "en": "Hello", "ko": "안녕"},
            {"de": "Hallo", "en": "Hello", "ko": "안녕하세요"},
        ]
    }
    repo = _repo(tmp_path, catalog=catalog)

    report = assemble.assemble(repo)

    assert len(report.problems) == 1
    assert "중복" in report.problems[0]


def test_주입_앞에_도는_규칙은_대장과_만난다(tmp_path: Path) -> None:
    """규칙이 고치는 것이 대장의 키인 문장 자체일 때 쓴다. 뒤에 돌면 한국어가 영영 안 들어간다."""
    catalog = {"strings": [{"de": "Hallo Welt", "en": "Hello world", "ko": "안녕 세계"}]}
    repo = _repo(tmp_path, catalog=catalog)
    (repo / "graft" / "rules.json").write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "name": "문구-넓히기",
                        "file": "FF14Accessibility/Plugin.cs",
                        "phase": "before",
                        "find": '    public static string Hello => IsGerman ? "Hallo" : "Hello";\n',
                        "replace": (
                            "    public static string Hello =>"
                            ' IsGerman ? "Hallo Welt" : "Hello world";\n'
                        ),
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = assemble.assemble(repo)

    assert report.problems == []
    assert report.orphans == []
    assert 'Pick("Hallo Welt", "Hello world", "안녕 세계")' in _built(repo)


def test_못_읽은_자리를_보고에_낸다(tmp_path: Path) -> None:
    """미적용 개수가 전부가 아니라는 것을 도구가 스스로 말한다."""
    repo = _repo(tmp_path)
    source = repo / "upstream" / "FF14Accessibility" / "Plugin.cs"
    source.write_text(
        PLUGIN.replace('IsGerman ? "Ok" : "Ok"', 'IsGerman ? Concat(a, b) : "off"'),
        encoding="utf-8",
    )

    report = assemble.assemble(repo)

    assert report.unreadable == ["Plugin.cs:11"]  # 축약 선언 두 줄이 앞에 들어간 뒤의 번호
    saved = json.loads((repo / "build" / "assemble-report.json").read_text(encoding="utf-8"))
    assert saved["unreadable"] == ["Plugin.cs:11"]


def test_대장의_한국어가_C샵_리터럴_규약을_어기면_실패한다(tmp_path: Path) -> None:
    """감싸기만 하고 인코딩하지 않는 것이 설계다. 그래서 규약을 어긴 값을 들이면 안 된다."""
    catalog = {"strings": [{"de": "Hallo", "en": "Hello", "ko": '안녕 "세계"'}]}
    repo = _repo(tmp_path, catalog=catalog)

    report = assemble.assemble(repo)

    assert len(report.problems) == 1
    assert "큰따옴표" in report.problems[0]


def test_escape한_따옴표는_통과한다(tmp_path: Path) -> None:
    catalog = {"strings": [{"de": "Hallo", "en": "Hello", "ko": '안녕 \\"세계\\"'}]}
    repo = _repo(tmp_path, catalog=catalog)

    assert assemble.assemble(repo).problems == []


def test_대장의_한국어에_줄바꿈이_있으면_실패한다(tmp_path: Path) -> None:
    catalog = {"strings": [{"de": "Hallo", "en": "Hello", "ko": "안녕\n세계"}]}
    repo = _repo(tmp_path, catalog=catalog)

    report = assemble.assemble(repo)

    assert len(report.problems) == 1
    assert "줄바꿈" in report.problems[0]


def test_앵커가_어긋나면_규칙_이름을_대고_실패한다(tmp_path: Path) -> None:
    """일부러 어긋나게 한 사본. 조용히 넘어가면 안 된다."""
    repo = _repo(tmp_path)
    source = repo / "upstream" / "FF14Accessibility" / "Plugin.cs"
    source.write_text(
        PLUGIN.replace("private static bool IsGerman", "private static bool Deutsch"),
        encoding="utf-8",
    )

    report = assemble.assemble(repo)

    assert len(report.problems) == 1
    assert "한국어-축약" in report.problems[0]


def test_보간_자리가_안_맞으면_경고로만_남는다(tmp_path: Path) -> None:
    """건너뛴 자리는 영어로 나간다. 침묵이 아니라 영어라서 실패가 아니다."""
    catalog = {"strings": [{"de": "Hallo {a}", "en": "Hello {a}", "ko": "{b} 안녕"}]}
    repo = _repo(tmp_path, catalog=catalog)
    source = repo / "upstream" / "FF14Accessibility" / "Plugin.cs"
    source.write_text(
        PLUGIN.replace('IsGerman ? "Hallo" : "Hello"', 'IsGerman ? $"Hallo {a}" : $"Hello {a}"'),
        encoding="utf-8",
    )

    report = assemble.assemble(repo)

    assert report.problems == []
    assert len(report.warnings) == 1
    assert "보간 자리" in report.warnings[0]


def test_CharaMake_사전_건수를_센다(tmp_path: Path) -> None:
    """삼항이 아니라 튜플 사전이라 이 도구가 보지 않는다. 개수만 낸다."""
    repo = _repo(tmp_path)
    services = repo / "upstream" / "FF14Accessibility" / "Services"
    services.mkdir(parents=True)
    (services / "CharaMakeIconText.cs").write_text(
        "static X()\n"
        "{\n"
        '    F("a", "b", 1u);\n'
        '    S("a", "b", "c", "d", 2u);\n'
        '    S("e", "f", "g", "h", 3u);\n'
        "}\n",
        encoding="utf-8",
    )

    report = assemble.assemble(repo)

    assert report.charamake["Services/CharaMakeIconText.cs"] == {"F": 1, "S": 2, "합계": 3}
