"""릴리스를 발행한다. `pack.py`가 낸 `dist`를 그대로 GitHub 릴리스에 올린다.

사용자가 새 판을 받는 길은 둘이고, 둘 다 이 릴리스의 자산을 가리킨다.

- 설치 프로그램 자기 갱신: `installer.json` (버전과 SHA-256)
- Dalamud 커스텀 저장소: `repo.json` (플러그인 압축 주소)

그래서 자산 넷이 **한 릴리스에** 같이 올라가야 한다. 하나라도 빠지면 받는 쪽은
오류가 아니라 "새 판이 없다"로 읽는다.

태그는 플러그인 버전이다. 설치 프로그램이 태그에서 `v`를 떼어 설치된 버전과
비교하기 때문이다(`InstallerService.ChoosePluginSourceAsync`).

## `gh`를 부르기 전에 게이트를 다 끝낸다

`gh`를 부르고 나면 바깥에 흔적이 남고, 되돌리는 길이 없다. 그래서 소스 게이트,
사람 승인, 노트 검사가 전부 그 앞이다.

## 옛 저장소에서 뺀 게이트 둘

옛 `run\\release.bat`에는 게이트가 둘 더 있었고, **둘 다 이 저장소에는 없는
것에 매여 있어서 빼 왔다.** 조용히 없앤 것이 아니라 옮길 자리가 없다.

1. **`pytest -m upstream_pending`** - 아직 한국어로 안 옮긴 안내 문장이 남았나를
   보던 자리다. 그 마커는 옛 저장소 전용이고 여기 `pyproject.toml`에는 없다.
   이 저장소에서 미번역을 세는 것은 조립이다 - `tools/assemble`이 미적용
   자리를 이름과 함께 보고하고, 그 보고는 `pack.py`의 조립 단계에서 나온다.
   **다만 그것은 세기만 하고 막지는 않는다** - 여기서 발행을 세우던 게이트는
   지금 없다
2. **`ko_words --require-dump`** - 게임에 없는 낱말을 그럴듯해서 쓴 것을 잡던
   자리다. `tools/ko-words`를 이 저장소로 안 옮겼다. 낱말 대장은
   `tools/ko-terms`가 갖는데 그쪽은 덤프를 요구하는 갈래가 없다

## 이번에는 안 돌린다

1판은 손으로 낸다. `--dry-run`으로 **무엇을 하려는지 찍어 보는 데까지**가
지금 쓰이는 길이다.

사용법:
    uv run python tools/pack/release.py --dry-run
    uv run python tools/pack/release.py
"""

from __future__ import annotations

import argparse
import functools
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO / "tools" / "common"))
sys.path.insert(0, str(REPO / "tools" / "kr-setup"))
sys.path.insert(0, str(REPO / "tools" / "pack-check"))
sys.path.insert(0, str(REPO / "tools" / "release-manifest"))

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다
import pack_check  # noqa: E402
import release_manifest  # noqa: E402

#: 원본 저장소. 릴리스 노트를 여기서 받아 커버리지 검사에 넘긴다.
UPSTREAM_REPO = "derbruedi/ff14-accessibility"

#: `dist/release`에 놓이는 노트 이름. 재는 쪽과 같은 값을 쓴다.
RELEASE_NOTES_NAME = pack_check.RELEASE_NOTES_NAME

#: 노트 원본이 있는 곳. 규약은 `docs/release-notes/README.md`가 갖는다.
NOTES_DIR = Path("docs") / "release-notes"

#: 검사기. 다른 도구가 만들고 있어서 **없을 수도 있다** - 없으면 선다.
NOTES_CHECK_SCRIPT = Path("tools") / "notes-check" / "notes_check.py"

# ── 사람이 거는 탈출구 ─────────────────────────────────────────────────────
#
# 이름을 옛 저장소 그대로 둔다. 사람이 손으로 거는 값이라 이름이 바뀌면
# 문서와 손버릇이 같이 낡는다.

#: 노트 본문을 사용자에게 보이고 승인을 받았다.
NOTES_APPROVED_VARIABLE = "FF14_NOTES_APPROVED"

#: 원본 절과 발화 목록을 사람이 대조했다.
NOTES_ACKED_VARIABLE = "FF14_NOTES_ACKED"

#: 원본 노트를 정말 못 받는 상태임을 사람이 확인했다.
UPSTREAM_UNREACHABLE_VARIABLE = "FF14_UPSTREAM_NOTES_UNREACHABLE"

#: 같은 판을 그대로 다시 올린다. 버전 검사를 건너뛴다.
SAME_VERSION_VARIABLE = "FF14_RELEASE_SAME_VERSION"

# ── 단계 이름 ──────────────────────────────────────────────────────────────

NOTES = "notes"
SOURCE_GATE = "source-gate"
APPROVAL = "approval"
NOTES_CHECK = "notes-check"
PUBLISH = "publish"


class ReleaseError(Exception):
    """한 단계도 못 시작한다. 무엇이 없어서인지 말하고 끝낸다."""


class Context(NamedTuple):
    """단계들이 공유하는 것. 경로와 이름 해석은 전부 여기서 끝난다."""

    repo: Path
    dist: Path
    release_dir: Path
    #: 플러그인 버전. 압축 안 매니페스트에서 그대로 뽑는다.
    version: str
    #: `v` + 버전. 설치 프로그램이 이 꼴을 기대한다.
    tag: str
    #: 노트 원본. **`dist`의 사본이 아니라 저장소 안의 것이다.**
    notes_source: Path
    gh_repo: str


class Step(NamedTuple):
    """한 단계. `run`이 0이 아니면 거기서 선다."""

    id: str
    label: str
    run: Callable[[], int]
    #: `--dry-run`이 찍는 줄. 실제로 무엇을 부르는지 그대로 적는다.
    plan: tuple[str, ...]


# ── 준비 ───────────────────────────────────────────────────────────────────


def missing_assets(dist: Path) -> list[Path]:
    """올릴 것 중 없는 것.

    루트 넷과 `release/`의 둘을 같이 본다. 루트만 보면 매니페스트 단계를
    건너뛴 상태가 안 걸리는데, 그 빠짐이야말로 받는 쪽에서 침묵으로 나타난다.
    """
    wanted = [dist / name for name in release_manifest.USER_FILES]
    wanted += [
        release_manifest.release_dir(dist) / name
        for name in (
            release_manifest.REPO_MANIFEST_NAME,
            release_manifest.INSTALLER_MANIFEST_NAME,
        )
    ]
    return [path for path in wanted if not path.is_file()]


def plugin_version(dist: Path) -> str:
    """압축 안 매니페스트의 버전. `release_manifest --print-version`과 같은 값이다.

    손으로 짓지 않는다 - 태그가 곧 플러그인 버전이고, 그것이 어긋나면 새 판이
    올라가 있어도 받는 쪽은 "이미 최신"으로 읽는다.
    """
    plugin = release_manifest.read_plugin_manifest(dist / release_manifest.ZIP_NAME)
    return str(release_manifest.build_repo_manifest(plugin)[0]["AssemblyVersion"])


def context(repo: Path = REPO, dist: Path | None = None) -> Context:
    """올릴 것이 다 있나 보고 버전을 읽는다. 못 하면 `ReleaseError`."""
    dist = dist if dist is not None else repo / "dist"

    missing = missing_assets(dist)
    if missing:
        lines = "\n".join(f"  {path}" for path in missing)
        raise ReleaseError(f"자산이 없다. `pack.py`를 먼저 돌린다:\n{lines}")

    try:
        version = plugin_version(dist)
    except release_manifest.ManifestError as error:
        raise ReleaseError(f"플러그인 버전을 못 읽었다: {error}") from error

    return Context(
        repo=repo,
        dist=dist,
        release_dir=release_manifest.release_dir(dist),
        version=version,
        tag=f"v{version}",
        notes_source=repo / NOTES_DIR / f"{version}.md",
        gh_repo=release_manifest.GH_REPO,
    )


def asset_paths(ctx: Context) -> list[Path]:
    """릴리스에 올릴 넷. 루트에서 둘, `release/`에서 둘이다."""
    in_root = {release_manifest.INSTALLER_NAME, release_manifest.ZIP_NAME}
    return [
        (ctx.dist if name in in_root else ctx.release_dir) / name
        for name in release_manifest.RELEASE_ASSETS
    ]


# ── 바깥 부르기 ────────────────────────────────────────────────────────────


def gh(args: list[str], capture: bool = False) -> str:
    """`gh`를 부른다. `capture`면 표준 출력을, 아니면 빈 문자열을 돌려준다.

    실패는 예외다 - 릴리스 절차에서 `gh`가 실패한 것을 그냥 넘기면 자산이
    반만 올라간 릴리스가 남는다.
    """
    result = subprocess.run(
        ["gh", *args],
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )
    if result.returncode != 0:
        raise ReleaseError(f"gh가 실패했다(코드 {result.returncode}): gh {' '.join(args)}")
    return result.stdout if capture else ""


def run_notes_check(ctx: Context, argv: list[str]) -> int:
    """검사기를 부른다. **`uv run`을 겹쳐 부르지 않는다** - 이미 그 안이다."""
    return subprocess.run([sys.executable, str(ctx.repo / NOTES_CHECK_SCRIPT), *argv]).returncode


# ── 단계들 ─────────────────────────────────────────────────────────────────


def copy_notes(ctx: Context) -> int:
    """노트 원본을 `dist/release`로 옮긴다.

    원본이 저장소 안에 있는 이유는 `dist`가 판마다 지워지기 때문이다. 옛
    저장소는 노트를 `dist`에 손으로 쓰고 올려서 **본문이 판마다 사라졌다.**
    """
    if not ctx.notes_source.is_file():
        print(f"[실패] 릴리스 노트가 없다: {ctx.notes_source}", file=sys.stderr)
        print("  규약은 docs/release-notes/README.md가 갖는다.", file=sys.stderr)
        return 1

    ctx.release_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ctx.notes_source, ctx.release_dir / RELEASE_NOTES_NAME)
    return 0


def source_gate(ctx: Context) -> int:
    """커밋 안 된 트리에서 나온 물건이 발행되는 것을 막는다."""
    return pack_check.main(["pack_check.py", "--source-gate"])


def approval(ctx: Context) -> int:
    """사람이 노트 본문을 봤나.

    기계가 보는 N1~N26은 형식만 본다. 항목이 빠졌는지, 설명이 이번 판 옆에서
    이미 안 통하는지, 문장이 어색한지는 **여기서만 걸린다.** `v5.94.0.0`에서
    사용자가 변경 항목 19개 중 14곳에 코멘트를 달았다.
    """
    if os.environ.get(NOTES_APPROVED_VARIABLE, "").strip():
        return 0

    print("[멈춤] 노트 본문을 사용자에게 보이고 승인을 받아야 한다.", file=sys.stderr)
    print(f"  본문: {ctx.notes_source}", file=sys.stderr)
    print(f"  승인받았으면 {NOTES_APPROVED_VARIABLE}=1 로 다시 돌린다", file=sys.stderr)
    return 1


def upstream_tag(version: str) -> str:
    """우리 판에 붙는 원본 태그. 앞 두 마디가 같다.

    우리 `5.95.0.0`에 원본 `v5.95`가 붙고, 우리 개정판(`5.91.0.1`)은 원본이 안
    바뀌었으므로 같은 `v5.91`을 본다.
    """
    major, minor = version.split(".")[:2]
    return f"v{major}.{minor}"


def upstream_notes(ctx: Context) -> str | None:
    """원본 릴리스 노트 본문. 못 받으면 `None`.

    커버리지 검사(N21~N23)가 이것을 본다. 없이 돌면 그 검사가 통째로 꺼진다.
    """
    try:
        body = gh(
            [
                "release",
                "view",
                upstream_tag(ctx.version),
                "--repo",
                UPSTREAM_REPO,
                "--json",
                "body",
                "-q",
                ".body",
            ],
            capture=True,
        )
    except (ReleaseError, OSError, subprocess.SubprocessError):
        return None
    return body if body.strip() else None


def latest_tag(ctx: Context) -> str | None:
    """직전 릴리스의 태그. 하나도 없으면 `None`."""
    try:
        return release_manifest.latest_release_tag(ctx.gh_repo)
    except release_manifest.ManifestError:
        return None


def upstream_unchanged(version: str, previous: str | None) -> bool:
    """원본 핀이 안 움직인 개정판인가. 앞 세 마디로 잰다.

    `docs/dev/release.md` 5절이 "핀을 옮기면 KR 마디를 0으로 되돌린다"고
    정하므로, 앞 세 마디가 같으면 핀이 안 움직인 것이다. 그런 판은 옮길 원본
    절이 없는데, N21은 선언으로 못 넘기는 위반이라 그 요구가 곧 발행 중단이 된다.
    """
    if not previous:
        return False
    head = lambda text: text.lstrip("vV").split(".")[:3]  # noqa: E731 - 세 마디 자르기 한 줄
    return head(previous) == head(version)


def check_notes(ctx: Context) -> int:
    """노트가 규칙에 맞나. 원본을 못 받으면 **여기서 선다.**

    조용히 넘기면 커버리지 검사가 꺼진 채로 돌고, 그러면 원본을 대조한 판과 안
    한 판이 화면에서 같아 보인다. 옛 저장소에서 `v5.92`가 원본의 도구 절을
    통째로 빼고도 개수 검사를 통과한 적이 있다.
    """
    script = ctx.repo / NOTES_CHECK_SCRIPT
    if not script.is_file():
        print(f"[실패] 노트 검사기가 없다: {script}", file=sys.stderr)
        print("  검사를 못 돌린 채로는 내지 않는다.", file=sys.stderr)
        return 1

    argv = ["--version", ctx.version, str(ctx.notes_source)]
    body = upstream_notes(ctx)

    if body is None:
        if not os.environ.get(UPSTREAM_UNREACHABLE_VARIABLE, "").strip():
            print(
                f"[실패] 원본 릴리스 노트를 못 받았다: {upstream_tag(ctx.version)}", file=sys.stderr
            )
            print("  커버리지 검사를 못 돌린 채로는 내지 않는다.", file=sys.stderr)
            print(
                f"  gh 인증을 확인하거나, 정말 못 받는 상태면 "
                f"{UPSTREAM_UNREACHABLE_VARIABLE}=1 로 다시 돌린다",
                file=sys.stderr,
            )
            return 1
        # 사람이 못 받는 것을 확인하고 일부러 넘긴 갈래다. 넘어간 것을 화면에 남긴다.
        tag = upstream_tag(ctx.version)
        print(f"[경고] 원본 릴리스 노트를 못 받았다: {tag}. 사람이 명시로 넘겼다")
        return run_notes_check(ctx, argv)

    workdir = Path(tempfile.mkdtemp(prefix="ff14acc-upnotes-"))
    try:
        upstream_file = workdir / "upstream-notes.md"
        upstream_file.write_text(body, encoding="utf-8")
        argv += ["--upstream-notes", str(upstream_file)]
        if os.environ.get(NOTES_ACKED_VARIABLE, "").strip():
            argv.append("--upstream-acked")
        if upstream_unchanged(ctx.version, latest_tag(ctx)):
            argv.append("--upstream-unchanged")
        return run_notes_check(ctx, argv)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def check_bump(ctx: Context) -> int:
    """이미 나간 것보다 버전이 올랐나. **자산을 올리기 직전에 부른다.**

    산출물이 바뀌었는데 버전이 그대로면 받는 쪽은 갱신을 아예 못 본다 - 설치
    프로그램의 `IsNewer`도 Dalamud도 버전만 본다. 오류가 아니라 침묵이라,
    올리고 나면 어디서도 안 드러난다.
    """
    if os.environ.get(SAME_VERSION_VARIABLE, "").strip():
        print(f"버전 검사를 건너뛴다 ({SAME_VERSION_VARIABLE}).")
        return 0
    return release_manifest.main(["release_manifest.py", "--dist", str(ctx.dist), "--check-bump"])


def tag_exists(ctx: Context) -> bool:
    """같은 태그의 릴리스가 이미 있나."""
    try:
        gh(["release", "view", ctx.tag, "--repo", ctx.gh_repo, "--json", "tagName"], capture=True)
    except (ReleaseError, OSError, subprocess.SubprocessError):
        return False
    return True


def release_title(ctx: Context) -> str:
    """릴리스 제목. 이름은 `tools/release-manifest`가 갖는 것과 같은 것이다."""
    return f"{release_manifest.PLUGIN_DISPLAY_NAME} {ctx.tag}"


def publish(ctx: Context) -> int:
    """릴리스를 내거나 덮어쓴다.

    **갈래에 따라 버전 검사의 자리가 다르다.** 새 태그면 만들기 전에 재고, 있는
    태그면 노트를 먼저 고치고 나서 잰다 - 막아야 하는 것은 자산을 올리는 것이지
    노트를 고치는 것이 아니다. 노트만 고치는 갈래까지 막으면, 이미 나간 판의
    오타를 고치려고 버전을 올리게 된다.
    """
    notes = ctx.release_dir / RELEASE_NOTES_NAME
    assets = [str(path) for path in asset_paths(ctx)]

    try:
        if not tag_exists(ctx):
            print("새 릴리스를 만든다.")
            if check_bump(ctx) != 0:
                return 1
            gh(
                [
                    "release",
                    "create",
                    ctx.tag,
                    "--repo",
                    ctx.gh_repo,
                    "--title",
                    release_title(ctx),
                    "--notes-file",
                    str(notes),
                    *assets,
                ]
            )
            return 0

        print("같은 태그가 이미 있다. 노트와 자산을 덮어쓴다.")
        # 노트도 같이 올린다. 제목만 고치면 판이 바뀌어도 받는 사람이 읽는 본문은
        # 첫 릴리스 때 그대로 남는다 - 오류가 아니라 침묵이다.
        gh(
            [
                "release",
                "edit",
                ctx.tag,
                "--repo",
                ctx.gh_repo,
                "--title",
                release_title(ctx),
                "--notes-file",
                str(notes),
            ]
        )
        if check_bump(ctx) != 0:
            return 1
        gh(["release", "upload", ctx.tag, "--repo", ctx.gh_repo, "--clobber", *assets])
        return 0
    except ReleaseError as error:
        print(f"[실패] {error}", file=sys.stderr)
        return 1


def steps(ctx: Context) -> list[Step]:
    """도는 순서. **`gh`를 처음 부르는 것은 마지막 하나뿐이다.**"""
    return [
        Step(
            NOTES,
            "노트 원본을 dist로 옮긴다",
            functools.partial(copy_notes, ctx),
            (f"{ctx.notes_source} -> {ctx.release_dir / RELEASE_NOTES_NAME}",),
        ),
        Step(
            SOURCE_GATE,
            "소스가 커밋되어 있나",
            functools.partial(source_gate, ctx),
            ("pack_check --source-gate",),
        ),
        Step(
            APPROVAL,
            "사람이 노트 본문을 봤나",
            functools.partial(approval, ctx),
            (f"{NOTES_APPROVED_VARIABLE} 가 있어야 지난다",),
        ),
        Step(
            NOTES_CHECK,
            "노트가 규칙에 맞나",
            functools.partial(check_notes, ctx),
            (
                f"원본 노트를 받는다: gh release view {upstream_tag(ctx.version)}"
                f" --repo {UPSTREAM_REPO}",
                f"notes_check --version {ctx.version} {ctx.notes_source}",
                f"못 받으면 선다 ({UPSTREAM_UNREACHABLE_VARIABLE} 로만 넘어간다)",
            ),
        ),
        Step(
            PUBLISH,
            "릴리스를 내거나 덮어쓴다",
            functools.partial(publish, ctx),
            (
                f"태그 {ctx.tag}, 저장소 {ctx.gh_repo}",
                f"제목 {release_title(ctx)}",
                "새 태그: 버전 검사 -> gh release create",
                "있는 태그: gh release edit -> 버전 검사 -> gh release upload --clobber",
                *(f"  자산 {path}" for path in asset_paths(ctx)),
            ),
        ),
    ]


def run_steps(plan: list[Step]) -> int:
    """차례로 돌리고 처음 실패한 자리에서 선다."""
    total = len(plan)
    for number, step in enumerate(plan, start=1):
        print(f"\n== {number}/{total} {step.label} ==")
        code = step.run()
        if code != 0:
            print(f"\n[멈춤] {number}/{total} {step.label} - 여기서 섰다.", file=sys.stderr)
            return code
    return 0


def dry_run(ctx: Context) -> int:
    """무엇을 하려는지만 찍는다. **바깥을 하나도 안 부른다.**"""
    print("== 릴리스 (찍어만 본다) ==")
    print(f"  태그    {ctx.tag}")
    print(f"  저장소  {ctx.gh_repo}")
    print(f"  노트    {ctx.notes_source}")
    print(f"  자산    {ctx.dist}")

    plan = steps(ctx)
    for number, step in enumerate(plan, start=1):
        print(f"\n{number}/{len(plan)} {step.label}")
        for line in step.plan:
            print(f"  {line}")

    print("\n아무것도 안 했다. 실제로 내려면 --dry-run 없이 돌린다.")
    return 0


def main(argv: list[str]) -> int:
    console.setup()
    parser = argparse.ArgumentParser(description="릴리스를 발행한다")
    parser.add_argument("--dist", help="자산이 있는 폴더. 안 주면 저장소의 dist")
    parser.add_argument(
        "--dry-run", action="store_true", help="무엇을 하려는지만 찍는다. 바깥을 안 부른다"
    )
    args = parser.parse_args(argv[1:])

    try:
        ctx = context(dist=Path(args.dist) if args.dist else None)
    except ReleaseError as error:
        print(f"== 릴리스: 시작 못 함 ==\n\n  - {error}", file=sys.stderr)
        return 1

    if args.dry_run:
        return dry_run(ctx)

    code = run_steps(steps(ctx))
    if code != 0:
        return code

    print("\n냈다. 받는 쪽이 보는 주소:")
    print(
        f"  {release_manifest.DOWNLOAD_REPO_URL}/releases/latest/download/"
        f"{release_manifest.INSTALLER_NAME}"
    )
    print(f"  {release_manifest.REPO_JSON_URL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
