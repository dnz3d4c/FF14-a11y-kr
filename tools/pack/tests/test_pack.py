"""배포 산출물 절차 테스트.

**이 도구는 바깥 프로그램을 부르는 껍질이다.** dotnet이 무엇을 내는지는 여기서
못 잰다. 그래서 재는 것을 둘로 좁힌다.

- **순서**: 어긋나면 조용히 틀린다. 게이트가 뒤로 가면 이미 만들어진 뒤에
  걸리고, 런처가 설치 프로그램 뒤로 가면 **옛 런처가 실린 설치 프로그램**이
  나온다 - 빌드는 성공하고 바로 가기만 낡는다
- **갈래**: 한 단계가 실패했는데 다음이 도는가. 도는 순간 검사를 안 지난
  물건이 `dist`에 놓인다
"""

import pytest

import pack


def context(tmp_path) -> pack.Context:
    """바깥을 안 부르는 자리에 쓰는 껍데기. 경로만 있으면 되는 검사들이 쓴다."""
    return pack.Context(
        repo=tmp_path,
        dist=tmp_path / "dist",
        dotnet=tmp_path / "dotnet.exe",
        hooks=tmp_path / "hooks",
    )


def ids(steps: list[pack.Step]) -> list[str]:
    return [step.id for step in steps]


# ── 순서 ───────────────────────────────────────────────────────────────────


def test_소스_게이트가_맨_앞이다(tmp_path):
    """뒤에 두면 몇 분을 버리고 나서 막힌다. 막는 것은 같아도 자리가 다르다."""
    assert ids(pack.steps(context(tmp_path)))[0] == pack.SOURCE_GATE


def test_런처가_설치_프로그램보다_먼저다(tmp_path):
    """설치 프로그램 csproj가 런처의 퍼블리시 산출물을 조건 없이 품는다.

    순서가 뒤바뀌면 빌드가 깨지는 것이 아니라 **옛 런처가 실린다.** 조립이
    `build/`를 통째로 지우므로 첫 실행에서는 빌드가 서고, 두 번째부터는 조용히
    낡은 것이 나간다.
    """
    order = ids(pack.steps(context(tmp_path)))
    assert order.index(pack.LAUNCHER) < order.index(pack.INSTALLER)


def test_단계_순서(tmp_path):
    """전체를 한 자리에 못박는다. 하나가 움직이면 여기가 먼저 빨개진다."""
    assert ids(pack.steps(context(tmp_path))) == [
        pack.SOURCE_GATE,
        pack.ASSEMBLE,
        pack.PLUGIN,
        pack.LAUNCHER,
        pack.INSTALLER,
        pack.COLLECT,
        pack.MANIFEST,
        pack.VERIFY,
    ]


def test_조립이_빌드보다_먼저다(tmp_path):
    """조립이 `build/`를 통째로 지우고 다시 만든다. 뒤에 오면 방금 빌드한 것이 사라진다."""
    order = ids(pack.steps(context(tmp_path)))
    assert order.index(pack.ASSEMBLE) < order.index(pack.PLUGIN)


# ── 갈래 ───────────────────────────────────────────────────────────────────


def test_한_단계가_실패하면_뒤가_안_돈다():
    ran = []

    def step(name: str, code: int) -> pack.Step:
        def run() -> int:
            ran.append(name)
            return code

        return pack.Step(id=name, label=name, run=run)

    steps = [step("첫째", 0), step("둘째", 1), step("셋째", 0)]
    assert pack.run_steps(steps) == 1
    assert ran == ["첫째", "둘째"]


def test_다_통과하면_0을_낸다():
    steps = [pack.Step(id=str(i), label=str(i), run=lambda: 0) for i in range(3)]
    assert pack.run_steps(steps) == 0


def test_빌드가_성공해도_산출물이_없으면_선다(tmp_path, monkeypatch):
    """dotnet이 0을 냈다는 것과 압축이 생겼다는 것은 다른 주장이다."""
    monkeypatch.setattr(pack, "run_dotnet", lambda *a, **k: 0)
    assert pack.build_plugin(context(tmp_path)) == 1


def test_런처_퍼블리시도_산출물을_다시_잰다(tmp_path, monkeypatch):
    monkeypatch.setattr(pack, "run_dotnet", lambda *a, **k: 0)
    assert pack.publish_launcher(context(tmp_path)) == 1


def test_dotnet이_실패하면_산출물을_안_본다(tmp_path, monkeypatch):
    """dotnet의 종료 코드가 먼저다. 산출물이 옛것으로 남아 있어도 실패다."""
    monkeypatch.setattr(pack, "run_dotnet", lambda *a, **k: 1)
    seed(tmp_path, pack.PLUGIN_ZIP)
    assert pack.build_plugin(context(tmp_path)) == 1


# ── 모으기 ─────────────────────────────────────────────────────────────────


def seed(root, relative, text="x"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def seed_all(root):
    seed(root, pack.INSTALLER_EXE)
    seed(root, pack.PLUGIN_ZIP)
    for source, _ in pack.USER_DOCS:
        seed(root, source)


def test_받는_사람이_보는_넷을_모은다(tmp_path):
    seed_all(tmp_path)
    ctx = context(tmp_path)
    assert pack.collect(ctx) == 0
    assert sorted(p.name for p in ctx.dist.iterdir()) == sorted(pack.DIST_ROOT_NAMES)


def test_안내_문서가_한글_이름으로_나간다(tmp_path):
    """받는 사람 폴더에 그 이름으로 보여야 하고, `pack_check`가 그 이름을 요구한다."""
    seed_all(tmp_path)
    ctx = context(tmp_path)
    pack.collect(ctx)
    assert (ctx.dist / "사용 안내.md").is_file()
    assert (ctx.dist / "단축키 목록.md").is_file()


def test_안내_문서의_내용이_그대로_간다(tmp_path):
    seed_all(tmp_path)
    seed(tmp_path, pack.USER_DOCS[0][0], "# 사용 안내\n한 줄.\n")
    ctx = context(tmp_path)
    pack.collect(ctx)
    assert (ctx.dist / "사용 안내.md").read_text(encoding="utf-8") == "# 사용 안내\n한 줄.\n"


@pytest.mark.parametrize("missing", [pack.INSTALLER_EXE, pack.PLUGIN_ZIP])
def test_원본이_하나라도_없으면_선다(tmp_path, missing):
    seed_all(tmp_path)
    (tmp_path / missing).unlink()
    assert pack.collect(context(tmp_path)) == 1


def test_안내_문서가_없어도_선다(tmp_path):
    """빠져도 빌드는 멀쩡하다. 받는 사람만 무엇부터 눌러야 하는지 모르게 된다."""
    seed_all(tmp_path)
    (tmp_path / pack.USER_DOCS[0][0]).unlink()
    assert pack.collect(context(tmp_path)) == 1


# ── 배선 ───────────────────────────────────────────────────────────────────


def test_마지막_검사에_이_기계의_참조를_넘긴다(tmp_path, monkeypatch):
    """`--e2e`가 KR Dalamud를 참조로 쓴다. 안 넘기면 검사가 딴 것을 잰다."""
    seen = []
    monkeypatch.setattr(pack.pack_check, "main", lambda argv: seen.append(argv) or 0)

    ctx = context(tmp_path)
    step = next(s for s in pack.steps(ctx) if s.id == pack.VERIFY)
    assert step.run() == 0

    argv = seen[0]
    assert "--e2e" in argv
    assert argv[argv.index("--kr-dalamud") + 1] == str(ctx.hooks)
    assert argv[argv.index("--dotnet") + 1] == str(ctx.dotnet)


def test_게이트가_소스만_본다(tmp_path, monkeypatch):
    """빌드하기 전이라 잴 것이 소스뿐이다. `--e2e`와 같은 진입점이라 인자로 가른다."""
    seen = []
    monkeypatch.setattr(pack.pack_check, "main", lambda argv: seen.append(argv) or 0)

    step = next(s for s in pack.steps(context(tmp_path)) if s.id == pack.SOURCE_GATE)
    step.run()
    assert "--source-gate" in seen[0]


def test_Dalamud를_못_찾으면_한_단계도_안_돈다(tmp_path, monkeypatch):
    """빌드하고 나서 참조가 없다고 하면 몇 분을 버린 뒤에 막히는 것과 같다."""
    monkeypatch.setattr(pack.pack_check, "dotnet_path", lambda: seed(tmp_path, "dotnet.exe"))
    monkeypatch.setattr(pack.kr_profile, "dalamud_hooks_dir", lambda: None)
    with pytest.raises(pack.PackError):
        pack.context(repo=tmp_path)


def test_dotnet을_못_찾으면_한_단계도_안_돈다(tmp_path, monkeypatch):
    monkeypatch.setattr(pack.pack_check, "dotnet_path", lambda: tmp_path / "없다.exe")
    monkeypatch.setattr(pack.kr_profile, "dalamud_hooks_dir", lambda: tmp_path)
    with pytest.raises(pack.PackError):
        pack.context(repo=tmp_path)
