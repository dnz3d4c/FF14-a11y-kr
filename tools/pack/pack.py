"""배포 산출물을 만든다. `dist/`가 이 도구의 결과다.

받는 사람이 여는 폴더에 넷을 낸다 - 설치 프로그램 EXE, 플러그인 압축, 그리고
안내 문서 둘. 기계만 읽는 매니페스트 둘은 `dist/release/`로 내린다. 그 구성을
실제로 재는 것은 `tools/pack-check`이고, 여기서는 만들어 놓는다.

## 이 파일은 얇다

로직은 이미 도구들에 있다. 조립은 `tools/assemble`, 매니페스트는
`tools/release-manifest`, 검사는 `tools/pack-check`가 갖는다. 여기가 갖는 것은
**순서 하나뿐이고, 그 순서가 이 도구의 전부다.**

## 순서가 왜 규칙인가

세 자리가 어긋나면 오류가 아니라 침묵으로 틀린다.

1. **소스 게이트가 맨 앞이다.** 어느 저장소에도 안 남은 트리로 만든 물건이
   나가는 것을 막는 자리인데, 뒤에 두면 다 만들고 나서 막힌다. 막는 것은
   같아도 그 사이의 몇 분이 버려진다
2. **조립이 빌드보다 앞이다.** 조립이 `build/`를 통째로 지우고 다시 만든다
   (`assemble.copy_upstream`). 뒤에 오면 방금 빌드한 것이 사라진다
3. **런처가 설치 프로그램보다 앞이다.** 설치 프로그램 csproj가 런처의 퍼블리시
   산출물을 `EmbeddedResource`로 **조건 없이** 끌어오고, 그 조건 없음이
   의도다(`docs/dev/installer.md`의 「빌드 순서」). 런처가 없으면 빌드가 거기서
   서야 한다 - 선택으로 만들면 끝까지 도는데 바로 가기만 조용히 안 놓이는
   설치 프로그램이 나오고, 그것은 화면을 못 보는 사람에게 아무 신호가 없는
   실패다

## 경로를 손으로 안 푼다

KR 프로필 루트와 Dalamud Hooks 폴더는 `tools/kr-setup/kr_profile.py`가 정한다.
Hooks는 이름이 버전이라 업데이터가 갱신할 때마다 바뀌므로 박아 두면 낡는다.

사용법:
    uv run python tools/pack/pack.py
    uv run python tools/pack/pack.py --dist 다른폴더
"""

from __future__ import annotations

import argparse
import functools
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO / "tools" / "common"))
sys.path.insert(0, str(REPO / "tools" / "assemble"))
sys.path.insert(0, str(REPO / "tools" / "kr-setup"))
sys.path.insert(0, str(REPO / "tools" / "pack-check"))
sys.path.insert(0, str(REPO / "tools" / "release-manifest"))

import assemble  # noqa: E402 - 위에서 경로를 넣어야 찾는다
import console  # noqa: E402
import kr_profile  # noqa: E402
import pack_check  # noqa: E402
import release_manifest  # noqa: E402

#: 플러그인 내부 이름. 프로젝트 폴더 이름이자 압축 이름이다.
INTERNAL_NAME = release_manifest.INTERNAL_NAME

# ── build/ 안의 자리 ───────────────────────────────────────────────────────
#
# 프레임워크 이름(`net10.0-windows`, `net8.0-windows`)과 런타임 이름(`win-x64`)은
# 각 csproj가 정한다. 여기 적힌 것과 갈라지면 **"산출물이 없다"로 크게 걸린다** -
# 조용히 옛것을 담는 갈래가 없으므로 박아 두는 값으로 둔다.

PLUGIN_PROJECT = Path("build") / INTERNAL_NAME / f"{INTERNAL_NAME}.csproj"
PLUGIN_ZIP = (
    Path("build") / INTERNAL_NAME / "bin" / "Release" / "net10.0-windows" / INTERNAL_NAME
) / "latest.zip"

LAUNCHER_PROJECT = Path("build") / "Launcher" / "FF14AccessibilityPlay.csproj"
LAUNCHER_EXE = (
    Path("build") / "Launcher" / "bin" / "Release" / "net10.0-windows" / "win-x64" / "publish"
) / pack_check.LAUNCHER_EXE

INSTALLER_PROJECT = Path("build") / "Installer" / "FF14AccessibilityInstaller.csproj"
INSTALLER_EXE = (
    Path("build") / "Installer" / "bin" / "Release" / "net8.0-windows" / "win-x64" / "publish"
) / release_manifest.INSTALLER_NAME

#: 저장소의 원본 -> `dist` 루트에 나갈 이름.
#:
#: **한글 이름 그대로 나간다.** 받는 사람이 폴더를 열었을 때 무엇을 읽어야 하는지
#: 알아야 하고, `tools/pack-check`가 그 이름을 요구한다.
#:
#: **여기에 줄을 더하는 것만으로는 사용자에게 안 닿는다.** 받는 사람이 실제로 쓰는
#: 목록은 `tools/release-manifest`의 `USER_FILES`이고, 거기 없으면 파일이 `dist`에만
#: 남는다. 그 빠짐은 오류가 아니라 침묵이다.
USER_DOCS = (
    (Path("docs") / "korean" / "README.ko.md", release_manifest.GUIDE_NAME),
    (Path("docs") / "korean" / "keys.md", release_manifest.KEYS_NAME),
)

#: `dist` 루트에 나오는 넷. 재는 것은 `tools/pack-check`고 여기는 만드는 쪽이다.
DIST_ROOT_NAMES = release_manifest.USER_FILES

# ── 단계 이름 ──────────────────────────────────────────────────────────────

SOURCE_GATE = "source-gate"
ASSEMBLE = "assemble"
PLUGIN = "plugin"
LAUNCHER = "launcher"
INSTALLER = "installer"
COLLECT = "collect"
MANIFEST = "manifest"
VERIFY = "verify"

#: 설치 실증을 개발 머신에서 이미 통과시켰다.
#:
#: **러너에는 게임이 없다.** 실증은 설치 프로그램을 버리는 프로필에 대고 실제로
#: 돌리는 것인데 그 안에 플레이 바로가기를 만드는 단계가 있어서, 게임이 없는
#: 기계에서는 원리적으로 못 지난다. 이름을 `release.py`의 탈출구들과 같은 꼴로
#: 둔다 - 사람이 손으로 거는 값이라 이름이 갈리면 문서와 손버릇이 같이 낡는다.
E2E_CHECKED_VARIABLE = "FF14_E2E_CHECKED"


class PackError(Exception):
    """한 단계도 못 시작한다. 무엇이 없어서인지 말하고 끝낸다."""


class Context(NamedTuple):
    """단계들이 공유하는 것. 경로 해석은 전부 여기서 끝난다."""

    repo: Path
    dist: Path
    #: .NET SDK. PATH의 dotnet은 런타임뿐이라 SDK에 안 닿는다.
    dotnet: Path
    #: KR Dalamud의 Hooks 폴더. 마지막 검사가 참조로 쓴다.
    hooks: Path


class Step(NamedTuple):
    """한 단계. `run`이 0이 아니면 거기서 선다."""

    id: str
    label: str
    run: Callable[[], int]


def context(repo: Path = REPO, dist: Path | None = None) -> Context:
    """바깥에서 얻어야 하는 것을 다 얻는다. 못 얻으면 `PackError`.

    **아무것도 만들기 전에 부른다.** 설치 프로그램까지 다 낸 뒤에 "Dalamud를
    못 찾았다"고 말하면, 막는 것은 같아도 몇 분이 버려진다.
    """
    dotnet = pack_check.dotnet_path()
    if not dotnet.is_file():
        raise PackError(f".NET SDK를 못 찾았다: {dotnet}. PATH의 dotnet은 런타임뿐이라 안 된다")

    hooks = kr_profile.dalamud_hooks_dir()
    if hooks is None or not hooks.is_dir():
        looked = Path(kr_profile.resolve_root()) / "addon" / "Hooks"
        raise PackError(
            f"KR Dalamud Hooks 폴더가 없다: {looked}. KR 달라무드 업데이터를 한 번 돌린다"
        )

    return Context(
        repo=repo, dist=dist if dist is not None else repo / "dist", dotnet=dotnet, hooks=hooks
    )


# ── 단계들 ─────────────────────────────────────────────────────────────────


def run_dotnet(ctx: Context, args: list[str], quiet: bool = True) -> int:
    """dotnet을 부른다. 종료 코드만 돌려주고 출력은 그대로 화면에 흘린다.

    MSBuild의 말을 영어로 고정한다. 한국어 출력은 콘솔 코드페이지를 타서
    로그에 깨진 글자로 남고, 실패했을 때 그 출력이 유일한 단서다.
    """
    command = [str(ctx.dotnet), *args]
    if quiet:
        command += ["-v", "quiet", "--nologo"]

    env = dict(os.environ)
    env["DOTNET_CLI_UI_LANGUAGE"] = "en"
    return subprocess.run(command, cwd=str(ctx.repo), env=env).returncode


def _made(path: Path, what: str) -> int:
    """산출물이 실제로 생겼나.

    **dotnet이 0을 냈다는 것과 파일이 생겼다는 것은 다른 주장이다.** 앞의 것만
    믿으면 다음 단계가 없는 파일을 복사하려다 엉뚱한 자리에서 걸린다.
    """
    if path.is_file():
        return 0
    print(f"[실패] {what}이 없다: {path}", file=sys.stderr)
    return 1


def source_gate(ctx: Context) -> int:
    """커밋 안 된 트리로 만든 물건이 나가는 것을 막는다. **빌드하기 전이다.**"""
    return pack_check.main(["pack_check.py", "--source-gate"])


def run_assemble(ctx: Context) -> int:
    """원본에 한국어를 얹어 `build/`를 만든다. 이 단계가 `build/`를 통째로 다시 만든다."""
    return assemble.main([])


def build_plugin(ctx: Context) -> int:
    """플러그인을 Release로 빌드한다. 산출물은 Dalamud가 받는 압축 하나다."""
    if run_dotnet(ctx, ["build", "-c", "Release", str(ctx.repo / PLUGIN_PROJECT)]) != 0:
        print("[실패] 플러그인 빌드가 깨졌다.", file=sys.stderr)
        return 1
    return _made(ctx.repo / PLUGIN_ZIP, "플러그인 압축")


def publish_launcher(ctx: Context) -> int:
    """게임과 업데이터를 함께 띄우는 런처. **설치 프로그램이 이것을 품고 나간다.**

    프레임워크 종속이다 - 설치 프로그램이 .NET 10을 먼저 보장하므로 런타임을
    한 벌 더 싣지 않는다.
    """
    if run_dotnet(ctx, ["publish", "-c", "Release", str(ctx.repo / LAUNCHER_PROJECT)]) != 0:
        print("[실패] 런처 빌드가 깨졌다.", file=sys.stderr)
        return 1
    return _made(ctx.repo / LAUNCHER_EXE, "런처 산출물")


def publish_installer(ctx: Context) -> int:
    """설치 프로그램을 자체 포함 단일 EXE로 낸다. 몇 분 걸린다.

    받는 쪽에 .NET 설치를 요구하지 않으려고 자체 포함으로 낸다. 조용히 두지
    않는 것은 **오래 걸리는 단계라 진행이 보여야 하기 때문**이다.
    """
    if (
        run_dotnet(
            ctx, ["publish", "-c", "Release", str(ctx.repo / INSTALLER_PROJECT)], quiet=False
        )
        != 0
    ):
        print("[실패] 설치 프로그램 빌드가 깨졌다.", file=sys.stderr)
        return 1
    return _made(ctx.repo / INSTALLER_EXE, "설치 프로그램")


def collect(ctx: Context) -> int:
    """받는 사람이 여는 폴더에 넷을 모은다.

    안내 문서 둘이 여기 끼는 이유는 편의가 아니다. 설치의 첫 단계가 그것을 읽는
    것인데 저장소에만 두면, 받는 사람은 무엇부터 눌러야 하는지 알 길이 없다.
    """
    pairs = [
        (ctx.repo / INSTALLER_EXE, ctx.dist / release_manifest.INSTALLER_NAME),
        (ctx.repo / PLUGIN_ZIP, ctx.dist / release_manifest.ZIP_NAME),
        *((ctx.repo / source, ctx.dist / name) for source, name in USER_DOCS),
    ]

    missing = [str(source) for source, _ in pairs if not source.is_file()]
    if missing:
        print("[실패] 모을 것이 없다:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1

    ctx.dist.mkdir(parents=True, exist_ok=True)
    for source, target in pairs:
        shutil.copy2(source, target)
    return 0


def write_manifests(ctx: Context) -> int:
    """릴리스에 같이 올릴 매니페스트 둘을 산출물에서 만든다.

    값을 손으로 안 적는다. 자기 갱신은 `installer.json`을, Dalamud 커스텀
    저장소는 `repo.json`을 읽고, 어긋나면 받는 쪽은 오류가 아니라 "새 판이
    없다"로 읽는다.
    """
    return release_manifest.main(["release_manifest.py", "--dist", str(ctx.dist)])


def verify(ctx: Context) -> int:
    """낸 것을 다시 잰다. 설치까지 실제로 돌려 보고 결과를 규칙으로 대조한다.

    **러너에서는 이 단계가 원리적으로 못 돈다.** 실증은 설치 프로그램을 버리는
    프로필에 대고 실제로 돌리는 것인데 그 안에 플레이 바로가기를 만드는 단계가
    있고, 러너에는 게임이 없다. 2026-09-04 첫 CI 발행이 거기서 죽었다.

    그래서 사람이 개발 머신에서 돌린 다음 그 사실을 선언한다. 검사가 없어지는
    것이 아니라 재는 자리가 옮겨갈 뿐이고, 넘어간 것을 화면에 남긴다 -
    `tools/pack/release.py`의 낱말 게이트와 같은 규약이다.
    """
    if os.environ.get(E2E_CHECKED_VARIABLE, "").strip():
        print(f"[경고] 설치 실증을 여기서 안 돌렸다. 사람이 {E2E_CHECKED_VARIABLE} 로 넘겼다")
        print("  개발 머신에서 pack_check --e2e 로 통과시켰다는 선언이다.")
        return 0

    return pack_check.main(
        [
            "pack_check.py",
            "--dist",
            str(ctx.dist),
            "--e2e",
            "--kr-dalamud",
            str(ctx.hooks),
            "--dotnet",
            str(ctx.dotnet),
        ]
    )


def steps(ctx: Context) -> list[Step]:
    """도는 순서. **이 목록이 이 도구의 전부다.**"""
    return [
        Step(SOURCE_GATE, "소스가 커밋되어 있나", functools.partial(source_gate, ctx)),
        Step(
            ASSEMBLE, "원본에 한국어를 얹어 build/를 만든다", functools.partial(run_assemble, ctx)
        ),
        Step(PLUGIN, "플러그인을 Release로 빌드한다", functools.partial(build_plugin, ctx)),
        Step(LAUNCHER, "런처를 퍼블리시한다", functools.partial(publish_launcher, ctx)),
        Step(
            INSTALLER,
            "설치 프로그램을 자체 포함 단일 EXE로 낸다 (몇 분)",
            functools.partial(publish_installer, ctx),
        ),
        Step(COLLECT, "받는 폴더에 넷을 모은다", functools.partial(collect, ctx)),
        Step(
            MANIFEST,
            "릴리스 매니페스트를 산출물에서 만든다",
            functools.partial(write_manifests, ctx),
        ),
        Step(VERIFY, "낸 것을 다시 잰다", functools.partial(verify, ctx)),
    ]


def run_steps(plan: list[Step]) -> int:
    """차례로 돌리고 **처음 실패한 자리에서 선다.**

    이어서 돌면 검사를 안 지난 물건이 `dist`에 놓인다. 그것이 나가면 무엇이
    틀렸는지 받는 쪽 화면에서나 드러난다.
    """
    total = len(plan)
    for number, step in enumerate(plan, start=1):
        print(f"\n== {number}/{total} {step.label} ==")
        code = step.run()
        if code != 0:
            print(f"\n[멈춤] {number}/{total} {step.label} - 여기서 섰다.", file=sys.stderr)
            return code
    return 0


def _report(dist: Path) -> None:
    """무엇이 나왔는지 이름과 크기로 적는다. 받는 사람이 여는 폴더가 먼저다."""
    print(f"\n== 끝: {dist} ==")
    for path in sorted(dist.rglob("*")):
        if path.is_file():
            print(f"  {path.relative_to(dist)}  {path.stat().st_size:,}바이트")


def main(argv: list[str]) -> int:
    console.setup()
    parser = argparse.ArgumentParser(description="배포 산출물을 만든다")
    parser.add_argument("--dist", help="받는 폴더. 안 주면 저장소의 dist")
    args = parser.parse_args(argv[1:])

    try:
        ctx = context(dist=Path(args.dist) if args.dist else None)
    except PackError as error:
        print(f"== 배포 산출물: 시작 못 함 ==\n\n  - {error}", file=sys.stderr)
        return 1

    code = run_steps(steps(ctx))
    if code != 0:
        return code

    _report(ctx.dist)
    print("\n확인 (설치는 안 하고 무엇을 찾았는지만 말한다):")
    print(f'  "{ctx.dist / release_manifest.INSTALLER_NAME}" --check')
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
