"""릴리스 발행 절차 테스트.

**바깥이 셋이다** - `gh`, `tools/notes-check`, `tools/release-manifest`. 그 셋이
무엇을 하는지는 여기서 못 잰다. 재는 것은 이 도구가 **언제 무엇을 부르는가**다.

특히 넷을 못박는다.

- **`gh`를 처음 부르기 전에 게이트가 다 끝난다.** 그 뒤로는 바깥에 흔적이 남고
  되돌리는 길이 없다
- **검사기에 원본 경로를 넘긴다.** 검사한 것과 올라가는 것이 갈리면 검사가
  아무것도 안 지킨다
- **원본 노트를 못 받으면 그냥 안 넘어간다.** 커버리지 검사가 조용히 꺼지면
  원본을 대조한 판과 안 한 판이 화면에서 같아 보인다
- **자산을 올리기 전에 버전을 잰다.** 산출물이 바뀌었는데 버전이 그대로면 받는
  쪽은 갱신을 아예 못 본다
"""

from pathlib import Path

import pytest

import release
import release_manifest

VERSION = "5.95.0.0"


def make_dist(tmp_path, *, notes=True):
    """자산 여섯이 다 있는 `dist`. 값은 안 보고 자리만 본다."""
    dist = tmp_path / "dist"
    release_dir = dist / release_manifest.RELEASE_DIR_NAME
    release_dir.mkdir(parents=True)
    for name in release_manifest.USER_FILES:
        (dist / name).write_text("x", encoding="utf-8")
    for name in (release_manifest.REPO_MANIFEST_NAME, release_manifest.INSTALLER_MANIFEST_NAME):
        (release_dir / name).write_text("{}", encoding="utf-8")
    if notes:
        source = tmp_path / "docs" / "release-notes" / f"{VERSION}.md"
        source.parent.mkdir(parents=True)
        source.write_text("# 5.95.0.0\n", encoding="utf-8")
    return dist


def context(tmp_path) -> release.Context:
    return release.Context(
        repo=tmp_path,
        dist=tmp_path / "dist",
        release_dir=tmp_path / "dist" / release_manifest.RELEASE_DIR_NAME,
        version=VERSION,
        tag=f"v{VERSION}",
        notes_source=tmp_path / "docs" / "release-notes" / f"{VERSION}.md",
        gh_repo="dnz3d4c/FF14-a11y-kr",
    )


def ids(steps) -> list[str]:
    return [step.id for step in steps]


# ── 준비 ───────────────────────────────────────────────────────────────────


def test_자산이_빠지면_한_단계도_안_돈다(tmp_path):
    dist = make_dist(tmp_path)
    (dist / release_manifest.ZIP_NAME).unlink()
    with pytest.raises(release.ReleaseError):
        release.context(repo=tmp_path)


def test_매니페스트가_빠져도_선다(tmp_path):
    """루트 넷만 보면 `pack.py`의 매니페스트 단계를 건너뛴 상태가 안 걸린다."""
    dist = make_dist(tmp_path)
    (dist / release_manifest.RELEASE_DIR_NAME / release_manifest.REPO_MANIFEST_NAME).unlink()
    with pytest.raises(release.ReleaseError):
        release.context(repo=tmp_path)


def test_태그는_플러그인_버전이다(tmp_path, monkeypatch):
    """설치 프로그램이 태그에서 v를 떼어 설치된 버전과 비교한다."""
    make_dist(tmp_path)
    monkeypatch.setattr(release, "plugin_version", lambda dist: VERSION)
    assert release.context(repo=tmp_path).tag == "v5.95.0.0"


def test_노트_원본은_저장소_안에_있다(tmp_path, monkeypatch):
    """`dist`는 판마다 지워진다. 원본이 거기 있으면 무엇을 발행했는지 못 되본다."""
    make_dist(tmp_path)
    monkeypatch.setattr(release, "plugin_version", lambda dist: VERSION)
    ctx = release.context(repo=tmp_path)
    assert ctx.notes_source == tmp_path / "docs" / "release-notes" / "5.95.0.0.md"


# ── 순서 ───────────────────────────────────────────────────────────────────


def test_단계_순서(tmp_path):
    assert ids(release.steps(context(tmp_path))) == [
        release.NOTES,
        release.SOURCE_GATE,
        release.WORDS,
        release.APPROVAL,
        release.NOTES_CHECK,
        release.PUBLISH,
    ]


def test_게이트가_전부_발행보다_앞이다(tmp_path):
    """`gh`를 부르고 나면 바깥에 흔적이 남는다. 되돌리는 길이 없다."""
    order = ids(release.steps(context(tmp_path)))
    publish = order.index(release.PUBLISH)
    for gate in (release.SOURCE_GATE, release.WORDS, release.APPROVAL, release.NOTES_CHECK):
        assert order.index(gate) < publish


def test_한_단계가_실패하면_뒤가_안_돈다():
    ran = []

    def step(name, code):
        return release.Step(id=name, label=name, run=lambda: ran.append(name) or code, plan=())

    assert release.run_steps([step("첫째", 0), step("둘째", 1), step("셋째", 0)]) == 1
    assert ran == ["첫째", "둘째"]


# ── 노트 ───────────────────────────────────────────────────────────────────


def test_노트를_dist로_옮긴다(tmp_path):
    make_dist(tmp_path)
    ctx = context(tmp_path)
    assert release.copy_notes(ctx) == 0
    copied = ctx.release_dir / release.RELEASE_NOTES_NAME
    assert copied.read_text(encoding="utf-8") == "# 5.95.0.0\n"


def test_노트가_없으면_선다(tmp_path):
    make_dist(tmp_path, notes=False)
    assert release.copy_notes(context(tmp_path)) == 1


# ── 낱말 게이트 ────────────────────────────────────────────────────────────


def stub_ko_words(tmp_path, code: int) -> Path:
    """받은 인자를 적어 두고 정해진 코드로 끝나는 가짜 낱말 검사기.

    함수를 바꿔치기하지 않고 **진짜 하위 프로세스로 돌린다.** 그래야
    `--require-dump`가 실제로 명령줄에 실리는지가 잡힌다. 그 깃발이 빠지는 것이
    이 게이트가 선 채로 아무것도 안 재는 유일한 길이라, 거기가 시험할 자리다.
    """
    script = tmp_path / release.KO_WORDS_SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    seen = tmp_path / "argv.txt"
    script.write_text(
        "import sys\n"
        f"open({str(seen)!r}, 'w', encoding='utf-8').write(' '.join(sys.argv[1:]))\n"
        f"raise SystemExit({code})\n",
        encoding="utf-8",
    )
    return seen


def test_낱말_검사를_덤프를_요구하며_부른다(tmp_path):
    seen = stub_ko_words(tmp_path, 0)
    assert release.check_words(context(tmp_path)) == 0
    assert seen.read_text(encoding="utf-8") == release.REQUIRE_DUMP_FLAG


def test_덤프가_없어_낱말_검사가_서면_발행도_선다(tmp_path):
    """되살린 게이트의 본체다.

    개발 머신에는 덤프가 있어서 이 갈래가 자연히 안 밟힌다. 그런데 막으려는
    사고는 **덤프가 없는 기계에서 발행하는 것**이라, 검사가 1을 돌려줬을 때
    발행이 실제로 서는지를 여기서 실증한다. 검사기 쪽에서 덤프가 없을 때 1을
    내는 것은 `tools/ko-words`의 `test_require_dump는_덤프가_없으면_실패한다`가
    따로 잰다 - 두 층이 맞물려야 게이트가 성립한다.
    """
    seen = stub_ko_words(tmp_path, 1)
    assert release.check_words(context(tmp_path)) == 1
    assert release.REQUIRE_DUMP_FLAG in seen.read_text(encoding="utf-8")


def test_낱말_검사기가_없으면_선다(tmp_path):
    """검사를 못 돌린 채로는 내지 않는다. 노트 검사기와 같은 규약이다."""
    assert release.check_words(context(tmp_path)) == 1


def test_사람이_로컬에서_쟀다고_말하면_넘어간다(tmp_path, monkeypatch, capsys):
    """러너에는 게임 덤프가 영영 없다. 그 하나 때문에 CI 발행 경로가 막힌다.

    덤프는 스퀘어에닉스의 게임 텍스트라 재배포하지 않기로 하고 `.gitignore`에
    넣었다. 그래서 이 게이트는 **개발 머신에서만 실물로 돌 수 있다.** 탈출구가
    없으면 발행을 CI로 옮기는 순간 게이트를 통째로 빼는 수밖에 없어진다.

    다른 탈출구들과 같은 규약이다 - 사람이 환경변수로 명시해야 하고, 넘어간
    것을 화면에 남긴다. 조용히 지나가면 잰 판과 안 잰 판이 같아 보인다.
    """
    monkeypatch.setenv(release.WORDS_CHECKED_VARIABLE, "1")
    # 검사기 파일조차 없는 상태에서도 지나야 한다 - 러너가 그럴 수 있다는 뜻이
    # 아니라, 이 갈래가 검사기를 아예 안 부른다는 것을 못 박는 것이다.
    assert release.check_words(context(tmp_path)) == 0
    assert "넘겼다" in capsys.readouterr().out


def test_탈출구가_비어_있으면_그대로_잰다(tmp_path):
    """빈 값은 선언이 아니다. `FF14_WORDS_CHECKED=` 는 안 건 것과 같다."""
    seen = stub_ko_words(tmp_path, 1)
    assert release.check_words(context(tmp_path)) == 1
    assert release.REQUIRE_DUMP_FLAG in seen.read_text(encoding="utf-8")


# ── 사람 승인 ──────────────────────────────────────────────────────────────


def test_승인이_없으면_선다(tmp_path, monkeypatch):
    """기계가 보는 N1~N26은 형식만 본다. 항목이 빠졌는지는 여기서만 걸린다."""
    monkeypatch.delenv(release.NOTES_APPROVED_VARIABLE, raising=False)
    assert release.approval(context(tmp_path)) == 1


def test_승인이_있으면_지난다(tmp_path, monkeypatch):
    monkeypatch.setenv(release.NOTES_APPROVED_VARIABLE, "1")
    assert release.approval(context(tmp_path)) == 0


# ── 원본 노트 ──────────────────────────────────────────────────────────────


def test_원본_태그는_앞_두_마디다():
    """우리 5.95.0.0에 원본 v5.95가 붙는다. 개정판도 같은 원본을 본다."""
    assert release.upstream_tag("5.95.0.0") == "v5.95"
    assert release.upstream_tag("5.91.0.1") == "v5.91"


def test_앞_세_마디가_같으면_핀이_안_움직인_개정판이다():
    assert release.upstream_unchanged("5.93.0.1", "v5.93.0.0")
    assert not release.upstream_unchanged("5.94.0.0", "v5.93.0.0")
    assert not release.upstream_unchanged("5.93.0.0", None)


class Spy:
    """검사기에 넘어간 인자와, 그때 파일에 실제로 들어 있던 원본 본문."""

    def __init__(self) -> None:
        self.argv: list[str] = []
        self.body: str | None = None

    def __call__(self, ctx, argv: list[str]) -> int:
        self.argv = argv
        if "--upstream-notes" in argv:
            self.body = Path(argv[argv.index("--upstream-notes") + 1]).read_text(encoding="utf-8")
        return 0


def stub_notes_check(monkeypatch, tmp_path) -> Spy:
    """검사기를 있는 것으로 만들고 호출을 잡는다."""
    script = tmp_path / "tools" / "notes-check" / "notes_check.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")

    spy = Spy()
    monkeypatch.setattr(release, "run_notes_check", spy)
    return spy


def test_원본_노트를_못_받으면_검사를_아예_안_부른다(tmp_path, monkeypatch):
    """조용히 넘기면 원본을 안 본 판과 다 옮긴 판이 화면에서 같아 보인다."""
    spy = stub_notes_check(monkeypatch, tmp_path)
    monkeypatch.setattr(release, "upstream_notes", lambda ctx: None)
    monkeypatch.delenv(release.UPSTREAM_UNREACHABLE_VARIABLE, raising=False)

    assert release.check_notes(context(tmp_path)) == 1
    assert spy.argv == []


def test_못_받는_것을_사람이_명시하면_원본_없이_돈다(tmp_path, monkeypatch):
    spy = stub_notes_check(monkeypatch, tmp_path)
    monkeypatch.setattr(release, "upstream_notes", lambda ctx: None)
    monkeypatch.setenv(release.UPSTREAM_UNREACHABLE_VARIABLE, "1")

    assert release.check_notes(context(tmp_path)) == 0
    assert "--upstream-notes" not in spy.argv


def test_받은_원본을_그대로_검사기에_넘긴다(tmp_path, monkeypatch):
    spy = stub_notes_check(monkeypatch, tmp_path)
    monkeypatch.setattr(release, "upstream_notes", lambda ctx: "원본 본문")
    monkeypatch.setattr(release, "latest_tag", lambda ctx: None)

    assert release.check_notes(context(tmp_path)) == 0
    assert spy.body == "원본 본문"


def test_검사기에_원본_경로를_넘긴다(tmp_path, monkeypatch):
    """`dist`의 사본이 아니라 저장소의 원본이다. 갈리면 검사가 아무것도 안 지킨다."""
    spy = stub_notes_check(monkeypatch, tmp_path)
    monkeypatch.setattr(release, "upstream_notes", lambda ctx: None)
    monkeypatch.setenv(release.UPSTREAM_UNREACHABLE_VARIABLE, "1")

    ctx = context(tmp_path)
    release.check_notes(ctx)
    assert str(ctx.notes_source) in spy.argv
    assert str(ctx.release_dir / release.RELEASE_NOTES_NAME) not in spy.argv


def test_사람이_원본을_짚었으면_그렇게_알린다(tmp_path, monkeypatch):
    spy = stub_notes_check(monkeypatch, tmp_path)
    monkeypatch.setattr(release, "upstream_notes", lambda ctx: "원본 본문")
    monkeypatch.setattr(release, "latest_tag", lambda ctx: None)
    monkeypatch.setenv(release.NOTES_ACKED_VARIABLE, "1")

    release.check_notes(context(tmp_path))
    assert "--upstream-acked" in spy.argv


def test_핀이_안_움직였으면_커버리지를_건너뛴다(tmp_path, monkeypatch):
    """네 번째 마디만 오르는 판은 옮길 원본 절이 없다."""
    spy = stub_notes_check(monkeypatch, tmp_path)
    monkeypatch.setattr(release, "upstream_notes", lambda ctx: "원본 본문")
    monkeypatch.setattr(release, "latest_tag", lambda ctx: "v5.95.0.0")

    release.check_notes(context(tmp_path))
    assert "--upstream-unchanged" in spy.argv


def test_검사기가_없으면_선다(tmp_path, monkeypatch):
    """부르는 쪽이 조용히 넘어가면 노트 규칙을 아무도 안 지키는 것이 된다."""
    monkeypatch.setattr(release, "upstream_notes", lambda ctx: None)
    monkeypatch.setenv(release.UPSTREAM_UNREACHABLE_VARIABLE, "1")
    assert release.check_notes(context(tmp_path)) == 1


# ── 발행 ───────────────────────────────────────────────────────────────────


def gh_verbs(monkeypatch, exists: bool) -> list[str]:
    """`gh`에 넘어간 하위 명령과 버전 검사를 **한 목록에** 순서대로 담는다."""
    verbs: list[str] = []

    def fake_gh(args, capture=False):
        verbs.append(" ".join(args[:2]))
        return ""

    monkeypatch.setattr(release, "gh", fake_gh)
    monkeypatch.setattr(release, "tag_exists", lambda ctx: exists)
    monkeypatch.setattr(release, "check_bump", bump(verbs, 0))
    return verbs


def bump(verbs: list[str], code: int):
    """버전 검사를 흉내 낸다. 부른 자리를 `gh` 호출과 같은 목록에 남긴다."""

    def fake(ctx) -> int:
        verbs.append("bump")
        return code

    return fake


def test_새_태그면_버전을_재고_만든다(tmp_path, monkeypatch):
    verbs = gh_verbs(monkeypatch, exists=False)
    assert release.publish(context(tmp_path)) == 0
    assert verbs == ["bump", "release create"]


def test_있는_태그면_노트를_먼저_고치고_그다음에_잰다(tmp_path, monkeypatch):
    """노트만 고치는 갈래를 안 막으려고 `edit`이 버전 검사보다 앞이다.

    막아야 하는 것은 **자산을 올리는 것**이다 - 산출물이 바뀌었는데 버전이
    그대로면 받는 쪽은 갱신을 아예 못 본다. 노트를 고치는 것은 그 부류가 아니다.
    """
    verbs = gh_verbs(monkeypatch, exists=True)
    assert release.publish(context(tmp_path)) == 0
    assert verbs == ["release edit", "bump", "release upload"]


def test_버전이_안_올랐으면_자산을_안_올린다(tmp_path, monkeypatch):
    verbs = gh_verbs(monkeypatch, exists=True)
    monkeypatch.setattr(release, "check_bump", bump(verbs, 1))
    assert release.publish(context(tmp_path)) == 1
    assert "release upload" not in verbs


def test_새_태그인데_버전이_안_올랐으면_안_만든다(tmp_path, monkeypatch):
    verbs = gh_verbs(monkeypatch, exists=False)
    monkeypatch.setattr(release, "check_bump", bump(verbs, 1))
    assert release.publish(context(tmp_path)) == 1
    assert "release create" not in verbs


def test_자산_넷을_한_릴리스에_올린다(tmp_path):
    """하나라도 빠지면 받는 쪽은 오류가 아니라 "새 판이 없다"로 읽는다."""
    paths = release.asset_paths(context(tmp_path))
    assert [p.name for p in paths] == list(release_manifest.RELEASE_ASSETS)


def test_매니페스트_둘은_release_폴더에서_올라간다(tmp_path):
    ctx = context(tmp_path)
    by_name = {p.name: p for p in release.asset_paths(ctx)}
    assert by_name[release_manifest.REPO_MANIFEST_NAME].parent == ctx.release_dir
    assert by_name[release_manifest.INSTALLER_NAME].parent == ctx.dist


# ── 찍어만 보기 ────────────────────────────────────────────────────────────


def test_찍어만_볼_때는_바깥을_안_부른다(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(release, "gh", lambda *a, **k: pytest.fail("gh를 불렀다"))
    monkeypatch.setattr(release, "run_notes_check", lambda *a, **k: pytest.fail("검사기를 불렀다"))
    monkeypatch.setattr(
        release, "run_ko_words", lambda *a, **k: pytest.fail("낱말 검사기를 불렀다")
    )

    assert release.dry_run(context(tmp_path)) == 0
    assert "v5.95.0.0" in capsys.readouterr().out


def test_찍어만_볼_때_단계를_다_보여_준다(tmp_path, capsys):
    release.dry_run(context(tmp_path))
    printed = capsys.readouterr().out
    for step in release.steps(context(tmp_path)):
        assert step.label in printed
