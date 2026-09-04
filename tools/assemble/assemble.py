"""원본 트리에 한국어를 얹어 빌드 가능한 트리를 만든다.

    upstream/ (서브모듈, 원본 태그 그대로)
      + korean/strings.json  문장 대장
      + kr/                  원본에 없는 신규 파일
      + replace/             원본 파일을 통째로 대체
      + graft/rules.json     원본 파일 안에 부분 삽입
      -> build/

## 왜 커밋이 아니라 빌드 단계인가

한국어를 원본 위에 커밋으로 얹으면 원본이 같은 파일을 고칠 때마다 충돌한다.
생성을 빌드 단계로 내리면 얹는 커밋이 없으니 충돌이 원리적으로 사라지고, 서브모듈
gitlink 하나가 원본 커밋의 단일 진실이 된다.

## 원본은 고치지 않는다

조립은 `build/` 안에서만 일어난다. `upstream/` 아래의 파일은 읽기만 한다. 이것이
이 저장소의 전제다.

## 미번역은 실패가 아니다

안 옮긴 문장은 영어로 나간다. 침묵은 고장과 구분이 안 되기 때문이다. 대신 이
도구가 그 자리를 세어 이름과 함께 보고하고, 모드도 실행 중에 로그에 남긴다.

사용법:
    uv run python tools/assemble/assemble.py
    uv run python tools/assemble/assemble.py --kr-revision 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import files
import graft
import scanner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다

#: 한국어 주입과 잔량 세기의 대상. `Installer/`와 `Launcher/`도 조립이 얹지만
#: 그쪽은 자체 사전(`Installer/Loc.cs`)이 세 언어를 들고 있어 대장을 안 거친다.
SOURCE_NAME = "FF14Accessibility"

#: 삼항이 아니라 `(De, En, BriefDe, BriefEn)` 튜플 사전이라 이 도구가 못 보는 파일.
#: 번역은 안 하고 건수만 센다.
TUPLE_TABLES = ["Services/CharaMakeIconText.cs", "Services/CharaMakeShapeText.cs"]

#: `replace/`의 사본이 어느 원본 판을 보고 쓰였는지 적어 둔 자리.
BASELINE_NAME = "upstream-baseline.json"

#: 버전을 찍는 csproj. 셋 다 조립이 끝난 트리에서의 상대 경로다.
VERSION_FILES = [
    "FF14Accessibility/FF14Accessibility.csproj",
    "Installer/FF14AccessibilityInstaller.csproj",
    "Launcher/FF14AccessibilityPlay.csproj",
]

#: csproj가 버전을 적는 태그 셋. 읽는 쪽이 저마다 달라서 늘 함께 쓴다.
VERSION_TAG = re.compile(r"<(Version|AssemblyVersion|FileVersion)>([^<]*)</\1>")

#: 버전 값의 모양. 세 마디이거나 네 마디이고, 우리가 이어 받는 것은 앞 세 마디다.
VERSION_VALUE = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+)(?:\.[0-9]+)?")

#: 튜플 사전의 등록 호출. 대문자 한 글자짜리 도우미(`F(`, `S(`)로 등록한다.
#: 도우미가 늘면 글자별로 따로 세어져 새 이름이 보고에 그대로 나타난다.
TABLE_CALL = re.compile(r"^[ \t]+([A-Z])\(", re.M)


@dataclass(frozen=True)
class Untranslated:
    """한국어가 없어 영어로 나갈 자리."""

    file: str
    line: int
    #: 그 자리를 감싸는 멤버 이름. 모드가 로그에 적는 이름과 같다.
    name: str
    en: str


@dataclass(frozen=True)
class Unreadable:
    """갈림길인 것은 알겠는데 파서가 못 읽은 자리.

    `scanner.Blind`에 파일 이름을 붙인 것이다. 파서는 글 하나만 보므로 그 글이 어느
    파일이었는지는 여기서만 안다.
    """

    file: str
    line: int
    end_line: int
    #: 그 자리를 감싸는 멤버 이름. 모드가 로그에 적는 이름과 같다.
    name: str
    #: 왜 못 읽었나.
    shape: str
    #: 그 자리의 앞부분 한 줄.
    excerpt: str

    @property
    def where(self) -> str:
        """`파일:행`. 여러 줄에 걸치면 범위로 적어 사람이 열어 볼 수 있게 한다."""
        if self.end_line <= self.line:
            return f"{self.file}:{self.line}"
        return f"{self.file}:{self.line}-{self.end_line}"


@dataclass
class Report:
    """조립 한 번의 결과."""

    #: 비어 있어야 조립이 성립한다.
    problems: list[str] = field(default_factory=list)
    #: 조립은 됐지만 사람이 봐야 할 것.
    warnings: list[str] = field(default_factory=list)
    catalog_rows: int = 0
    #: 버전 넷째 자리에 찍은 한국어판 개정 마디.
    kr_revision: int = 0
    #: csproj에 실제로 찍은 버전. `파일 -> 값`.
    versions: dict[str, str] = field(default_factory=dict)
    #: 한국어를 써 넣은 자리의 수. 같은 문장이 여러 자리에 있으면 여러 번 센다.
    applied_sites: int = 0
    #: 그 자리들이 쓴 대장 행의 수.
    applied_rows: int = 0
    #: 대장에는 있는데 소스에서 못 만난 쌍. 원본이 그 문장을 고쳤다는 신호다.
    orphans: list[tuple[str, str]] = field(default_factory=list)
    untranslated: list[Untranslated] = field(default_factory=list)
    #: 갈림길인 것은 알겠는데 못 읽은 자리. 미적용에도 안 잡히므로 따로 낸다.
    unreadable: list[Unreadable] = field(default_factory=list)
    charamake: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


# --- 대장 ------------------------------------------------------------------


#: C# 리터럴 안에서 백슬래시 뒤에 올 수 있는 글자.
ESCAPES = set('\\"nrt0')


def literal_fault(ko: str) -> str | None:
    """C# 리터럴 안에 그대로 들어갈 값인지. 어긋나면 까닭을, 맞으면 None.

    대장의 값은 **리터럴 안에 들어갈 내용 그대로**다(`korean/strings.json`의 `key`).
    큰따옴표는 이미 백슬래시로 escape되어 있어야 하고, 그래서 조립은 값을 감싸기만
    하고 인코딩하지 않는다. 인코더를 넣으면 이중 escape가 된다.

    규약을 어긴 값은 여기서 막는다. 대장은 사람이 손으로 고치는 파일이라 언젠가
    escape 안 된 따옴표가 들어오고, 그때 조용히 깨진 C#을 내는 것보다 그 행을 지목하고
    멈추는 편이 낫다.

    ## 보간 자리 안은 잣대가 다르다

    자리 안은 식이라 그 안의 따옴표는 escape하면 안 된다. `\\"`는 C# 문법 오류다. 그래서
    자리 안은 빼고 본다. 자리 밖의 escape 안 된 따옴표는 여전히 리터럴을 그 자리에서
    끝내 버리므로 지금처럼 막는다. 자리의 모양 자체는 `scanner.body_fault`가 본다.
    """
    if "\n" in ko or "\r" in ko:
        return "줄바꿈이 그대로 들어 있다"
    outside = scanner.outside_holes(ko)
    i = 0
    while i < len(outside):
        if outside[i] == "\\":
            if i + 1 >= len(outside) or outside[i + 1] not in ESCAPES:
                return f"C#이 모르는 이스케이프다: {ko[i : i + 2]}"
            i += 2
            continue
        if outside[i] == '"':
            return "escape 안 된 큰따옴표가 있다"
        i += 1
    return None


def load_catalog(path: Path) -> dict[tuple[str, str], str]:
    """`(독일어, 영어) -> 한국어`.

    독일어와 영어를 **둘 다** 키로 쓴다. 같은 독일어 낱말이 문장마다 다른 영어를
    갖기 때문에 독일어만으로는 자리를 못 가른다.
    """
    rows = json.loads(path.read_text(encoding="utf-8"))["strings"]
    catalog: dict[tuple[str, str], str] = {}
    for row in rows:
        key = (row["de"], row["en"])
        if not row["ko"].strip():
            raise ValueError(f"한국어가 비어 있다: {row['en'][:60]}")
        if key in catalog:
            raise ValueError(f"같은 쌍이 중복이다: {row['en'][:60]}")
        # 모양을 먼저 본다. 자리의 짝이 깨져 있으면 어디까지가 자리인지가 안 정해지고,
        # 그러면 리터럴 규약을 자리 밖에서만 보는 판단도 믿을 수 없다.
        fault = scanner.body_fault(row["ko"]) or literal_fault(row["ko"])
        if fault is not None:
            raise ValueError(f"{fault}: {row['en'][:60]}")
        catalog[key] = row["ko"]
    return catalog


def orphans(
    catalog: dict[tuple[str, str], str], seen: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """대장에는 있는데 소스에서 못 만난 쌍."""
    found = set(seen)
    return [key for key in catalog if key not in found]


# --- 파일 ------------------------------------------------------------------


def source_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.cs"))
        if "obj" not in path.parts and "bin" not in path.parts
    ]


def _relative_files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


# --- 절차 ------------------------------------------------------------------


def copy_upstream(upstream: Path, build: Path) -> None:
    """원본 트리를 통째로 복사한다.

    `FF14Accessibility/`만으로는 빌드가 안 된다. csproj가 `..\\LICENSE`와
    `..\\THIRD-PARTY-NOTICES.md`를 `Content`로 끌어오기 때문이다.
    """
    if build.exists():
        shutil.rmtree(build)
    shutil.copytree(upstream, build, ignore=shutil.ignore_patterns(".git", "bin", "obj"))


def inject_korean(build: Path, catalog: dict[tuple[str, str], str], report: Report) -> None:
    """대장의 한국어를 소스에 써 넣는다."""
    root = build / SOURCE_NAME
    if not root.is_dir():
        report.problems.append(f"조립 대상이 없다 - {SOURCE_NAME}/")
        return

    applied: list[tuple[str, str]] = []

    for path in source_files(root):
        before = files.read(path)
        result = scanner.rewrite(before, catalog)
        applied += result.applied

        name = path.relative_to(root).as_posix()
        report.warnings += [f"{name}:{problem}" for problem in result.bad_slots]
        if result.text != before:
            files.write(path, result.text)

    report.applied_sites = len(applied)
    report.applied_rows = len(set(applied))


def apply_replace(repo: Path, build: Path, report: Report) -> None:
    """원본 파일을 우리 사본으로 통째로 갈아 끼운다.

    이것이 위험한 부류다. 원본의 개선을 조용히 덮어쓸 수 있어서, 원본의 그 파일이
    기준선을 적어 둔 판 이후로 바뀌었으면 알린다.
    """
    source = repo / "replace"
    if not source.is_dir():
        return

    baseline = _load_baseline(source)
    for name in _relative_files(source):
        if name == BASELINE_NAME:
            continue
        # 원본을 본다. `build/`의 같은 파일은 한국어 주입이 이미 손댔을 수 있어서
        # 지문이 원본의 것이 아니다.
        original = repo / "upstream" / name
        if not original.is_file():
            report.problems.append(
                f"replace에 있는데 원본에 없다 - {name}. kr에 있어야 할 파일이다"
            )
            continue

        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        if name not in baseline:
            report.warnings.append(f"replace 기준선이 없다 - {name}. 지금 원본은 {digest}다")
        elif baseline[name] != digest:
            report.warnings.append(
                f"replace의 원본이 기준선 이후로 바뀌었다 - {name}. 우리 사본이 낡았는지 본다"
            )
        shutil.copy2(source / name, build / name)


def _load_baseline(source: Path) -> dict[str, str]:
    path = source / BASELINE_NAME
    if not path.is_file():
        return {}
    recorded = json.loads(path.read_text(encoding="utf-8"))["files"]
    return {str(name): str(digest) for name, digest in recorded.items()}


def copy_kr(repo: Path, build: Path, report: Report) -> None:
    """원본에 없는 신규 파일을 얹는다."""
    source = repo / "kr"
    if not source.is_dir():
        return

    for name in _relative_files(source):
        target = build / name
        if target.exists():
            report.problems.append(
                f"kr에 있는데 원본에도 있다 - {name}. replace에 있어야 할 파일이다"
            )
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)


def load_graft(repo: Path, report: Report) -> list[graft.Rule]:
    """덧대기 규칙을 한 번만 읽는다. 모양이 깨져 있으면 보고에 담고 빈 목록을 돌려준다.

    던지게 두면 조립이 traceback으로 죽는다. 그러면 CI의 실패 사유 하나("조립 실패")가
    그때만 다른 모양으로 나오고, 보고 파일도 안 남아 무엇이 왜 실패했는지가 로그에만
    남는다. 실패는 언제나 같은 자리에서 같은 모양으로 보여야 한다.
    """
    path = repo / "graft" / "rules.json"
    if not path.is_file():
        return []
    try:
        return graft.load_rules(path)
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        report.problems.append(f"덧대기 규칙의 모양이 깨졌다 - {error}")
        return []


def load_revision(path: Path) -> int:
    """`korean/version.json`의 개정 마디. 모양이 깨져 있으면 ValueError.

    앞 세 마디는 여기 없다. 그것은 원본이 자기 사정으로 정하는 값이라 우리가 적을 자리가
    아니다.
    """
    value = json.loads(path.read_text(encoding="utf-8"))["kr_revision"]
    # bool을 따로 거르는 까닭은 파이썬에서 bool이 int이기 때문이다. `true`를 그냥
    # 통과시키면 csproj에 `5.95.0.True`가 적힌다.
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"kr_revision은 0 이상의 정수다 - {value!r}")
    return value


def stamp_versions(build: Path, revision: int, report: Report) -> None:
    """csproj 셋의 버전 태그를 `<그 파일의 앞 세 마디>.<개정>`으로 맞춘다.

    ## 왜 넷째 자리인가

    원본 핀을 그대로 두고 한국어만 고친 판을 내려면 올릴 자리가 필요하다. 앞 세 마디가
    같은 채로 다시 내면 설치 프로그램의 `IsNewer`가 거짓이 되어, 자기 갱신이 오류가
    아니라 **침묵으로** 선다.

    ## 왜 셋을 함께 쓰나

    설치 프로그램은 `Version`을 읽고 달라무드는 `AssemblyVersion`을 읽는다. 원본은
    `Version`만 세 마디로 적으므로 그대로 두면 두 쪽이 서로 다른 값을 말하고, 어느 쪽이
    맞는지는 실행해 봐야만 드러난다.

    ## 앞 세 마디는 읽는다

    우리가 정하지 않는다. 설치 프로그램의 버전은 플러그인과 달리 태그 이름과 아무 관계가
    없고(`v5.95`인데 `1.2.2`다) 업스트림이 자기 사정으로 올린다.
    """
    for name in VERSION_FILES:
        target = build / name
        if not target.is_file():
            report.problems.append(f"버전을 찍을 파일이 없다 - {name}")
            continue

        text = files.read(target)
        parsed = [(value, VERSION_VALUE.fullmatch(value)) for _, value in VERSION_TAG.findall(text)]
        if not parsed:
            report.problems.append(f"버전 태그가 하나도 없다 - {name}")
            continue

        broken = [value for value, match in parsed if match is None]
        if broken:
            report.problems.append(f"버전 마디가 숫자가 아니다 - {name}의 {broken[0]}")
            continue

        heads = {match.group(1) for _, match in parsed if match is not None}
        if len(heads) > 1:
            report.problems.append(
                f"한 파일 안에서 앞 세 마디가 갈렸다 - {name}의 {sorted(heads)}. "
                "어느 태그를 따를지 우리가 정할 일이 아니다"
            )
            continue

        version = f"{heads.pop()}.{revision}"
        files.write(target, VERSION_TAG.sub(rf"<\1>{version}</\1>", text))
        report.versions[name] = version


# --- 세기 ------------------------------------------------------------------


def survey(build: Path) -> tuple[list[tuple[str, str]], list[Untranslated], list[Unreadable]]:
    """조립이 끝난 트리를 훑는다. (만난 쌍, 영어로 나갈 자리, 못 읽은 자리).

    조립 전이 아니라 **조립이 끝난 뒤**에 세는 까닭은 그것이 실제로 나갈 트리이기
    때문이다. 판정 대상은 잔량이다.

    고아도 여기서 나온 쌍으로 계산한다. `kr/`의 파일은 자기 문장을 한국어까지 넣어
    갖고 있는데 그 파일들은 복사 단계에서야 트리에 들어온다. 주입 단계의 결과로
    고아를 세면 그 문장들이 매번 고아로 잡혀, 원본이 문장을 고쳤다는 진짜 신호가
    가짜 열 줄에 묻힌다.

    못 읽은 자리를 같이 내는 까닭은 **미적용 개수가 전부가 아니기** 때문이다. 중첩
    삼항처럼 파서의 손 밖인 모양은 미적용에도 안 잡히므로, 그런 자리가 조용히 늘면
    도구의 숫자만 보는 사람에게는 아무 신호가 없다.
    """
    root = build / SOURCE_NAME
    if not root.is_dir():
        return [], [], []

    seen: list[tuple[str, str]] = []
    untranslated: list[Untranslated] = []
    unreadable: list[Unreadable] = []
    for path in source_files(root):
        text = files.read(path)
        name = path.relative_to(root).as_posix()
        sites, blind = scanner.scan(text)
        unreadable += [
            Unreadable(
                file=name,
                line=spot.line,
                end_line=spot.end_line,
                name=spot.name,
                shape=spot.shape,
                excerpt=spot.excerpt,
            )
            for spot in blind
        ]
        for site in sites:
            seen.append((site.de, site.en))
            if site.ko is not None:
                continue
            untranslated.append(
                Untranslated(
                    file=name,
                    line=site.line,
                    name=scanner.member_name(text, site.start),
                    en=site.en,
                )
            )
    return seen, untranslated, unreadable


def count_tuple_tables(build: Path) -> dict[str, dict[str, int]]:
    """튜플 사전의 등록 건수. 번역하지 않고 개수만 낸다."""
    root = build / SOURCE_NAME
    counts: dict[str, dict[str, int]] = {}
    for name in TUPLE_TABLES:
        path = root / name
        if not path.is_file():
            continue
        per_helper: dict[str, int] = {}
        for helper in TABLE_CALL.findall(files.read(path)):
            per_helper[helper] = per_helper.get(helper, 0) + 1
        per_helper["합계"] = sum(per_helper.values())
        counts[name] = per_helper
    return counts


# --- 전체 ------------------------------------------------------------------


def assemble(repo: Path, kr_revision: int | None = None) -> Report:
    """원본에 한국어를 얹어 `build/`를 만든다.

    `kr_revision`을 주면 `korean/version.json`의 값 대신 그것을 찍는다. 저장소의 값은
    안 고친다 - 시험 삼아 한 번 다르게 조립해 보는 길이다.
    """
    report = Report()
    build = repo / "build"

    try:
        catalog = load_catalog(repo / "korean" / "strings.json")
    except (ValueError, KeyError) as error:
        report.problems.append(f"대장의 모양이 깨졌다 - {error}")
        return report
    report.catalog_rows = len(catalog)

    if kr_revision is None:
        try:
            kr_revision = load_revision(repo / "korean" / "version.json")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            report.problems.append(f"개정 마디를 못 읽었다 - {error}")
            return report
    report.kr_revision = kr_revision

    rules = load_graft(repo, report)

    copy_upstream(repo / "upstream", build)
    report.problems += graft.apply_rules(rules, build, graft.BEFORE)
    inject_korean(build, catalog, report)
    apply_replace(repo, build, report)
    copy_kr(repo, build, report)
    report.problems += graft.apply_rules(rules, build, graft.AFTER)
    # 버전은 맨 마지막이다. `kr/`와 `replace/`가 복사된 뒤여야 런처 csproj가 트리에 있고,
    # `after` 규칙도 csproj를 건드리므로 그 뒤라야 우리 값이 남는다.
    stamp_versions(build, kr_revision, report)

    seen, report.untranslated, report.unreadable = survey(build)
    report.orphans = orphans(catalog, seen)
    report.charamake = count_tuple_tables(build)
    _save(build, report)
    return report


def _save(build: Path, report: Report) -> None:
    """기계가 읽을 보고. CI가 이것을 산출물로 남긴다."""
    document = {
        "ok": report.ok,
        "problems": report.problems,
        "warnings": report.warnings,
        "catalog_rows": report.catalog_rows,
        "kr_revision": report.kr_revision,
        "versions": report.versions,
        "applied_sites": report.applied_sites,
        "applied_rows": report.applied_rows,
        "orphans": [{"de": de, "en": en} for de, en in report.orphans],
        "untranslated": [
            {"file": site.file, "line": site.line, "name": site.name, "en": site.en}
            for site in report.untranslated
        ],
        "unreadable": [
            {
                "file": site.file,
                "line": site.line,
                "end_line": site.end_line,
                "name": site.name,
                "shape": site.shape,
                "excerpt": site.excerpt,
            }
            for site in report.unreadable
        ],
        "charamake": report.charamake,
    }
    (build / "assemble-report.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _print(report: Report) -> None:
    """화면에 나가는 줄이라 마크다운 장식은 안 쓴다. 스크린리더가 그대로 읽는다."""
    print(f"개정 {report.kr_revision} - 버전 넷째 자리")
    for name, version in report.versions.items():
        print(f"  {name} = {version}")
    print(f"대장 {report.catalog_rows}행")
    print(f"적용 {report.applied_sites}곳 (대장 {report.applied_rows}행)")
    print(f"고아 {len(report.orphans)}행 - 대장에 있는데 소스에서 못 만난 쌍")
    for _, en in report.orphans:
        print(f"  {en[:70]}")
    print(f"미적용 {len(report.untranslated)}곳 - 영어로 나갈 자리")
    for site in report.untranslated:
        where = f"{site.file}:{site.line}"
        print(f"  {where} {site.name or '(이름 없음)'} - {site.en[:60]}")
    print(f"못 읽음 {len(report.unreadable)}곳 - 갈림길인데 이 파서의 손 밖이라 위 숫자에 없다")
    for blind in report.unreadable:
        print(f"  {blind.where} {blind.name or '(이름 없음)'} [{blind.shape}] {blind.excerpt}")

    for name, counts in report.charamake.items():
        parts = ", ".join(f"{key} {value}" for key, value in sorted(counts.items()))
        print(f"튜플 사전 {name}: {parts} - 이 도구가 보지 않는다")

    for warning in report.warnings:
        print(f"살펴볼 것: {warning}")


def main(argv: list[str] | None = None) -> int:
    console.setup()
    parser = argparse.ArgumentParser(description="원본에 한국어를 얹어 build/를 만든다.")
    parser.add_argument(
        "--kr-revision",
        type=int,
        help="한국어판 개정 마디. 주면 korean/version.json 대신 이 값을 찍는다 - 저장소는 그대로다",
    )
    args = parser.parse_args(argv)
    if args.kr_revision is not None and args.kr_revision < 0:
        parser.error("--kr-revision은 0 이상이다")

    repo = Path(__file__).resolve().parents[2]
    if not (repo / "upstream" / SOURCE_NAME).is_dir():
        print(
            "원본 서브모듈이 비어 있다. git submodule update --init 을 먼저 실행한다.",
            file=sys.stderr,
        )
        return 1

    report = assemble(repo, kr_revision=args.kr_revision)
    _print(report)

    if report.problems:
        print("\n조립이 실패했다:", file=sys.stderr)
        for problem in report.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"\n조립했다: {repo / 'build'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
