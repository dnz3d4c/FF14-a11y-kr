"""배포 산출물이 정말 '바닐라'인지 검사한다.

배포 산출물 둘(`dist\\FF14Accessibility.zip`,
`dist\\FF14AccessibilityInstaller-KR.exe`)에 **이 머신의 것이 섞였는지**와,
그 산출물이 **Dalamud가 정식 플러그인으로 읽는 모양인지**를 본다.

**`dist`를 만드는 절차는 이 저장소에 아직 없다.** 조립(`tools/assemble`)이
`build/`까지 내고, 거기서 배포 산출물을 뽑는 단계는 다음에 세운다. 그때까지
이 도구는 **무엇이 없어서 못 재는지만 말한다** - 잴 것이 없다고 조용히
통과하면 검사가 도는 것과 안 도는 것이 같은 얼굴이 된다.

네 갈래다.

1. **소스 게이트(`--source-gate`)** - 어느 저장소에도 안 남은 트리로 만든
   물건이 나가려는가. 원본 서브모듈이 기록된 커밋에 있고 깨끗한가, 우리
   소스에 커밋 안 된 변경이 없는가
2. **위생** - 압축 안에 들어갈 것만 들어 있나, 사용자 이름·홈 경로·설정 파일이
   섞이지 않았나, 매니페스트가 빌드와 같은 버전인가
3. **모양** - 설치 결과가 `installedPlugins\\<이름>\\<버전>\\<이름>.dll`인가.
   Dalamud는 **버전으로 파싱되지 않는 폴더를 지운다**(`PluginManager.CleanupPlugins`),
   그래서 폴더 이름은 취향이 아니라 적재 여부를 가르는 조건이다
4. **실물 검증(`--e2e`)** - 설치 프로그램을 버리는 프로필 루트
   (`FF14ACC_KR_PROFILE`)에 대고 `--install`로 실제로 돌려 보고 그 결과를 위
   규칙으로 잰다. 설치 프로그램은 창이라 눈으로만 볼 수 있는데, 이 경로는
   기계가 볼 수 있다

**왜 방향을 뒤집나**: "설치 프로그램이 성공이라고 말했다"와 "파일이 Dalamud가
보는 자리에 있다"는 다른 주장이다. 앞의 것만 믿다가 갈린 적이 있다.

사용법:
    uv run python tools/pack-check/pack_check.py [--dist DIR] [--e2e]
    uv run python tools/pack-check/pack_check.py --source-gate
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO / "tools" / "common"))
sys.path.insert(0, str(REPO / "tools" / "kr-setup"))
sys.path.insert(0, str(REPO / "tools" / "release-manifest"))

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다
import kr_profile  # noqa: E402
import release_manifest  # noqa: E402

#: 플러그인 내부 이름. Dalamud는 폴더 이름·DLL 이름·매니페스트가 다 이것이길 요구한다.
INTERNAL_NAME = "FF14Accessibility"

#: 게임과 업데이터를 함께 띄우는 런처. 설치 프로그램이 자기 안에 품고 있다가
#: `%LOCALAPPDATA%\\FF14Accessibility`에 꺼내 놓고 바로가기를 건다.
LAUNCHER_EXE = "FF14AccessibilityPlay.exe"

#: 받는 폴더에 함께 나가는 안내 문서. 저장소의 원본은 `docs/korean/README.ko.md`다.
GUIDE_NAME = "사용 안내.md"

#: 안내 문서 4장의 키만 모은 목록. 저장소의 원본은 `docs/korean/keys.md`이고,
#: **정본은 사용 안내 쪽이고 이것은 사본이다.**
KEYS_NAME = "단축키 목록.md"

#: 릴리스에 같이 올라가는 매니페스트 둘. `tools/release-manifest`가 만든다.
#: 여기서는 **나갈 자리에 있나**만 본다 - 값이 맞나는 그 도구의 `--check`가,
#: 릴리스에 올라갔나는 `--release`가 잰다.
RELEASE_MANIFESTS = (
    release_manifest.REPO_MANIFEST_NAME,
    release_manifest.INSTALLER_MANIFEST_NAME,
)

#: 사람이 안 여는 것이 들어가는 자리. `dist` 루트는 **받는 사람에게 그대로 줄
#: 수 있는 폴더**로 두고 여기에 기계용을 내린다 - 사용 안내가 "압축을 풀면 그
#: 안에 넷이 들어 있습니다"라고 세어 주는 그 폴더라, 거기 파일이 많으면 무엇을
#: 눌러야 하는지 헷갈린다.
RELEASE_DIR_NAME = release_manifest.RELEASE_DIR_NAME

#: 릴리스 노트. 사람이 쓰고, 받는 사람이 "이번에 뭐가 바뀌었나"를 읽는
#: 유일한 자리다. 무엇을 어떻게 적나는 `docs/dev/release-notes-rules.md`가 갖는다.
RELEASE_NOTES_NAME = "release-notes.md"

#: Dalamud가 "공식 저장소에서 왔다"에 쓰는 값(`SpecialPluginSource.MainRepo`).
#: 설치 프로그램이 **처음에 쓰는** 값이고, 설정에 저장소를 등록한 뒤 아래
#: `KR_REPO_URL`로 옮긴다. 끝나고도 이 값이면 그 단계가 안 돈 것이다.
OFFICIAL_SOURCE = "OFFICIAL"

#: 우리 저장소. 설치가 끝난 매니페스트의 `InstalledFromUrl`이 이것이어야 하고,
#: 같은 문자열이 `dalamudConfig.json`의 `ThirdRepoList`에도 있어야 한다.
#:
#: **여기서 다시 적지 않고 `tools/release-manifest`에서 가져온다.** 그쪽이
#: `repo.json`을 내는 자리이고, 이쪽은 그 결과가 설치된 모양을 잰다. 두 벌로
#: 들고 있으면 **검사는 통과하는데 실물이 다른 상태**가 만들어진다.
#:
#: **`OFFICIAL`로 두면 왜 안 되나**: 적재는 된다. 그런데 그건 공식 저장소가
#: 우리를 목록에 갖고 있다는 주장이고 사실이 아니라서, Dalamud가
#: `IsDecommissioned`를 세운다(`LocalPlugin.cs:196-198`). 그러면 프로필을 다시
#: 적용할 때 - 캐릭터를 바꿀 때가 그렇다 - 켜지지 않고 경고만 남는다
#: (`ProfileManager.cs:258`). 갱신도 안 된다.
#:
#: Dalamud가 `==`로 대조하므로 대소문자와 후행 슬래시까지 같아야 한다.
KR_REPO_URL = release_manifest.REPO_JSON_URL

#: 전투 경고 전용 음성 채널(SAPI)이 쓰는 것.
SPEECH_NAME = "System.Speech.dll"

#: 압축에 들어가도 되는 정확한 이름들.
ALLOWED_EXACT = {
    f"{INTERNAL_NAME}.dll",
    f"{INTERNAL_NAME}.json",
    f"{INTERNAL_NAME}.deps.json",
    f"{INTERNAL_NAME}.pdb",
    "Tolk.dll",
    "nvdaControllerClient64.dll",
    SPEECH_NAME,
    "LICENSE",
    "THIRD-PARTY-NOTICES.md",
}

#: 이름이 판마다 늘어나는 것들. NAudio는 우리가 고르는 목록이 아니라 의존성이다.
ALLOWED_PATTERNS = (re.compile(r"^NAudio(\.[A-Za-z]+)?\.dll$"),)

#: 압축 안에서 유일하게 허용하는 폴더.
#:
#: **`System.Speech`는 NuGet이 같은 이름으로 두 벌을 준다.** 루트에 오는 것은
#: 플랫폼 중립판(~310KB)이고 윈도 밖에서 `PlatformNotSupportedException`을
#: 던지는 껍데기다. 진짜 윈도 구현(~685KB)은 이 경로 아래에 있고, csproj의
#: `FlattenSpeechRuntime`이 그것을 루트에 덮어쓴다. 그래서 배포물에는 같은
#: 내용이 두 자리에 들어온다.
#:
#: **틀리면 조용하다.** 덮어쓰기는 `Condition="Exists(...)"`라서 경로가
#: 어긋나면 MSBuild 경고 한 줄만 남기고 넘어가고, 그 경고는 아무도 안 본다.
#: 적재도 되고 이 검사만 통과하면 **첫 전투 경고에서 던진다.**
#: 그래서 이름이 아니라 CRC로 재고, `net9.0`을 못박지 않는다 - 못박으면
#: 패키지가 다음 TFM으로 올라간 날 진짜 사고가 아닌 자리에서 빨개진다.
SPEECH_RID = re.compile(r"^runtimes/win/lib/net\d+\.\d+/System\.Speech\.dll$")

#: 배포물에 있으면 안 되는 것. 설치 프로그램이 설치할 때 **붙이는** 필드라서,
#: 압축 안에 이미 있으면 누군가 설치된 사본을 다시 압축했다는 뜻이다.
LOCAL_ONLY_FIELDS = ("InstalledFromUrl", "WorkingPluginId", "Disabled", "ScheduledForDeletion")


def _text_variants(needle: str) -> tuple[bytes, ...]:
    """.NET 바이너리는 문자열을 UTF-16으로 갖는다. 둘 다 본다."""
    return needle.encode("utf-8"), needle.encode("utf-16-le")


def personal_traces(blob: bytes, needles: list[str]) -> list[str]:
    """바이트 안에서 발견된 개인 흔적. 없으면 빈 목록."""
    return [n for n in needles if any(v in blob for v in _text_variants(n))]


def default_needles() -> list[str]:
    """이 머신을 가리키는 문자열들. 인자로 받는 이유는 테스트 때문이다.

    빌드 경로는 **일부러 뺐다.** .NET 어셈블리는 PDB 경로를 디버그 디렉토리에
    박고, 그건 모든 .NET 빌드가 하는 일이라 개인 설정이 아니다. 여기서 막는
    것은 **사람을 가리키는 것** - 계정 이름과 홈 경로다.
    """
    user = os.environ.get("USERNAME", "")
    needles = [str(Path.home())]
    if user:
        needles.append(user)
    return [n for n in needles if n]


def speech_problems(crcs: dict[str, int]) -> list[str]:
    """경고 음성 DLL이 진짜 윈도 구현인지. 어긋나면 첫 전투 경고에서 던진다.

    재는 것은 크기가 아니라 CRC다. 두 자리가 같은 내용이면 루트에 있는 것이
    `runtimes` 아래에서 온 윈도 구현이라는 뜻이고, 그것 말고 다른 증거는
    압축 안에 없다. 근거는 `SPEECH_RID` 주석.
    """
    rid = [name for name in crcs if SPEECH_RID.match(name)]
    if SPEECH_NAME not in crcs:
        return [f"있어야 할 파일이 없다: {SPEECH_NAME}"]
    if not rid:
        return [
            f"{SPEECH_NAME}은 있는데 runtimes 아래 원본이 없다 - "
            "루트에 있는 것이 윈도 구현인지 잴 방법이 없다"
        ]
    if any(crcs[name] != crcs[SPEECH_NAME] for name in rid):
        return [
            f"{SPEECH_NAME}이 runtimes 아래 원본과 내용이 다르다 - "
            "덮어쓰기가 안 돌아 중립판이 그대로 나간다. 첫 전투 경고에서 던진다"
        ]
    return []


def zip_problems(crcs: dict[str, int]) -> list[str]:
    """압축 목록에서 규칙을 어긴 것들. 이름마다 CRC를 받는다."""
    problems = []
    for name in crcs:
        if SPEECH_RID.match(name):
            continue
        if "/" in name or "\\" in name:
            problems.append(f"압축 안에 폴더가 있다: {name}")
            continue
        if name in ALLOWED_EXACT:
            continue
        if any(p.match(name) for p in ALLOWED_PATTERNS):
            continue
        problems.append(f"목록에 없는 파일이 들어 있다: {name}")

    for required in (f"{INTERNAL_NAME}.dll", f"{INTERNAL_NAME}.json"):
        if required not in crcs:
            problems.append(f"있어야 할 파일이 없다: {required}")
    return problems + speech_problems(crcs)


def manifest_problems(manifest: dict, csproj_version: str | None) -> list[str]:
    """배포용 매니페스트 검사. 설치 뒤의 매니페스트는 규칙이 다르다."""
    problems = []
    if manifest.get("InternalName") != INTERNAL_NAME:
        problems.append(f"InternalName이 {manifest.get('InternalName')!r}다")

    version = manifest.get("AssemblyVersion")
    if not version:
        problems.append("AssemblyVersion이 없다")
    elif csproj_version and version != csproj_version:
        problems.append(f"버전이 빌드 설정과 다르다: 매니페스트 {version}, csproj {csproj_version}")

    if not isinstance(manifest.get("DalamudApiLevel"), int):
        problems.append("DalamudApiLevel이 없거나 숫자가 아니다")

    for field in LOCAL_ONLY_FIELDS:
        if field in manifest:
            problems.append(f"설치 뒤에나 붙는 필드가 배포물에 있다: {field}")
    return problems


def parse_version(text: str) -> tuple[int, ...] | None:
    """`Version.TryParse`가 받아들이는 모양인가. 2~4마디 숫자만 통과한다."""
    parts = text.split(".")
    if not 2 <= len(parts) <= 4:
        return None
    if not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def installed_layout_problems(plugin_root: Path) -> list[str]:
    """설치 결과가 Dalamud가 읽는 모양인가."""
    if not plugin_root.is_dir():
        return [f"설치 폴더가 없다: {plugin_root}"]

    version_dirs = [d for d in plugin_root.iterdir() if d.is_dir()]
    if len(version_dirs) != 1:
        names = ", ".join(sorted(d.name for d in version_dirs)) or "(없음)"
        return [f"버전 폴더가 하나여야 하는데 {len(version_dirs)}개다: {names}"]

    version_dir = version_dirs[0]
    problems = []
    if parse_version(version_dir.name) is None:
        # Dalamud가 이런 폴더를 지운다. 조용히 사라지고 플러그인만 없어진다.
        problems.append(f"버전 폴더 이름이 버전이 아니다: {version_dir.name}")

    dll = version_dir / f"{INTERNAL_NAME}.dll"
    if not dll.is_file():
        problems.append(f"DLL이 폴더 이름과 안 맞거나 없다: {dll}")

    manifest_path = version_dir / f"{INTERNAL_NAME}.json"
    if not manifest_path.is_file():
        return problems + [f"매니페스트가 없다: {manifest_path}"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = manifest.get("InstalledFromUrl")
    if source != KR_REPO_URL:
        # 두 갈래를 갈라서 말한다. `OFFICIAL`이면 설치는 됐는데 저장소로 옮기는
        # 마지막 단계가 안 돈 것이고, 그 밖이면 어느 저장소와도 안 맞아 고아다.
        problems.append(
            f"InstalledFromUrl이 아직 {OFFICIAL_SOURCE!r}다. 저장소로 옮기는 단계가 안 돌았다"
            if source == OFFICIAL_SOURCE
            else f"InstalledFromUrl이 {source!r}다. {KR_REPO_URL!r}가 아니면 "
            f"Dalamud가 고아로 보고 적재를 건너뛴다"
        )
    if manifest.get("Disabled") is not False:
        problems.append("매니페스트가 Disabled를 거짓으로 갖고 있지 않다")
    if manifest.get("AssemblyVersion") != version_dir.name:
        problems.append(
            f"폴더 이름과 매니페스트 버전이 다르다: "
            f"{version_dir.name} vs {manifest.get('AssemblyVersion')}"
        )
    if not manifest.get("WorkingPluginId"):
        problems.append("WorkingPluginId가 비었다. 프로필 항목과 이어지지 않는다")
    return problems


def working_plugin_id(plugin_root: Path) -> str | None:
    """설치된 사본의 WorkingPluginId. 없으면 None."""
    for version_dir in sorted(plugin_root.glob("*")):
        manifest = version_dir / f"{INTERNAL_NAME}.json"
        if manifest.is_file():
            return json.loads(manifest.read_text(encoding="utf-8")).get("WorkingPluginId")
    return None


def config_problems(config: dict, expected_id: str | None, dev_dll: str) -> list[str]:
    """dalamudConfig.json이 정식 경로를 가리키고 dev 흔적이 없는가."""
    problems = []

    entries = (config.get("DefaultProfile") or {}).get("Plugins", {}).get("$values", [])
    ours = [e for e in entries if e.get("InternalName") == INTERNAL_NAME]
    if len(ours) != 1:
        problems.append(f"기본 프로필의 우리 항목이 {len(ours)}개다. 하나여야 한다")
    else:
        entry = ours[0]
        if entry.get("IsEnabled") is not True:
            problems.append("기본 프로필에서 꺼져 있다")
        if expected_id and entry.get("WorkingPluginId") != expected_id:
            problems.append(
                "프로필 항목의 WorkingPluginId가 매니페스트와 다르다: "
                f"{entry.get('WorkingPluginId')} vs {expected_id}"
            )

    locations = (config.get("DevPluginLoadLocations") or {}).get("$values", [])
    if any(str(loc.get("Path", "")).lower() == dev_dll.lower() for loc in locations):
        problems.append("dev 적재 경로가 남아 있다. 같은 모드가 두 번 적재된다")

    dev_settings = config.get("DevPluginSettings") or {}
    if any(k.lower() == dev_dll.lower() for k in dev_settings):
        problems.append("DevPluginSettings 항목이 남아 있다")

    # 매니페스트가 가리키는 저장소가 여기 없으면 그게 고아다. 대소문자를 접지
    # 않는 이유는 Dalamud가 `==`로 재기 때문이다 - 철자가 다르면 다른 저장소다.
    repos = (config.get("ThirdRepoList") or {}).get("$values", [])
    ours_repo = [r for r in repos if r.get("Url") == KR_REPO_URL]
    if not ours_repo:
        problems.append(f"저장소가 등록되지 않았다: {KR_REPO_URL}")
    elif ours_repo[0].get("IsEnabled") is not True:
        problems.append("저장소는 등록됐는데 꺼져 있다")

    return problems


# ── 소스 게이트 ────────────────────────────────────────────────────────────
#
# 막는 것은 하나다 - **어느 저장소에도 안 남은 트리로 만든 물건이 나가는 것.**
# 커밋 안 된 워킹트리에서 나온 산출물이 발행 직전까지 간 적이 있고, 그 트리는
# 어느 저장소에도 안 남아서 무엇이 나갔는지 되짚을 방법이 없었다.
#
# 이 저장소에서 그 질문은 둘로 갈린다. 원본은 서브모듈이라 **우리 커밋에
# gitlink 한 줄로만** 남고, 우리 것은 `kr/`·`replace/`·`graft/`·`korean/`·
# `tools/`에 파일로 남는다. `build/`는 그 둘에서 나오는 생성물이라 여기서
# 안 본다.

#: 원본 서브모듈의 자리. 저장소는 이 경로에 커밋 하나(gitlink)를 기록한다.
UPSTREAM_DIR = "upstream"

#: 우리가 손으로 쓰는 것이 전부 여기 있다.
SOURCE_DIRS = ("kr", "replace", "graft", "korean", "tools")

#: 몇 줄까지 보여 줄까. 전문을 뱉으면 무엇을 해야 하는지가 묻힌다.
DIRTY_LINES = 10


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def gitlink_commit(repo: Path) -> str | None:
    """저장소가 기록한 원본 커밋. 스테이징 먼저, 없으면 HEAD, 그마저 없으면 None.

    **스테이징을 먼저 읽는다.** `git add upstream`을 막 마친 커밋 직전
    상태에서 HEAD를 먼저 보면, 방금 옮긴 기록을 어긋났다고 잡는다.
    """
    for ref in (f":{UPSTREAM_DIR}", f"HEAD:{UPSTREAM_DIR}"):
        result = _git("rev-parse", ref, cwd=repo)
        if result.returncode == 0:
            return result.stdout.strip()
    return None


def is_own_repo(path: Path) -> bool:
    """그 폴더 자신이 저장소인가.

    **`.git`이 있나로 묻지 않는다.** 서브모듈로 받으면 `.git`이 디렉토리가
    아니라 파일이고, 아예 안 받아졌으면 빈 폴더라 **그 안에서 물으면 부모
    저장소가 답한다.** 그 답을 그대로 믿으면 "안 받아졌다"가 "기록과 다르다"로
    둔갑해서, 받으면 되는 상황에 엉뚱한 곳을 뒤지게 된다.
    """
    if not path.is_dir():
        return False
    result = _git("rev-parse", "--show-toplevel", cwd=path)
    return result.returncode == 0 and Path(result.stdout.strip()) == path.resolve()


def upstream_problems(repo: Path) -> list[str]:
    """받아 놓은 원본이 저장소가 기록한 그 커밋이고 손대지 않은 상태인가.

    어긋나면 **`build/`가 어느 원본 판에서 나왔는지가 안 정해진다.** 조립은
    `upstream/`의 워킹트리를 읽으므로, 기록과 다른 커밋이 놓여 있으면 나간
    물건의 원본이 gitlink이 가리키는 것과 다르다.
    """
    upstream = repo / UPSTREAM_DIR
    recorded = gitlink_commit(repo)
    if recorded is None:
        return [
            f"저장소에 {UPSTREAM_DIR} 기록이 없다 - 나가는 물건이 어느 원본에서 나왔는지 못 적는다"
        ]

    if not is_own_repo(upstream):
        return [f"{UPSTREAM_DIR}이 안 받아졌다: {upstream}. `git submodule update --init`로 받는다"]

    problems = []
    head = _git("rev-parse", "HEAD", cwd=upstream).stdout.strip()
    if head != recorded:
        problems.append(
            f"{UPSTREAM_DIR}이 기록과 다른 커밋에 있다: 받아 놓은 것 {head[:12]}, "
            f"기록 {recorded[:12]}. build가 어느 원본 판에서 나왔는지가 안 정해진다"
        )

    dirty = _git("status", "--porcelain", cwd=upstream).stdout.splitlines()
    left = [line for line in dirty if line.strip()]
    if left:
        problems.append(
            f"{UPSTREAM_DIR}에 손댄 것이 있다 - 원본은 읽기만 하는 것이 이 저장소의 전제다:"
        )
        problems += [f"  {line}" for line in left[:DIRTY_LINES]]
    return problems


def source_dirty(repo: Path) -> list[str]:
    """우리 소스에 커밋 안 된 변경. 추적 안 되는 새 파일도 센다.

    새 파일이 빌드에 들어가는 것도 같은 사고다 - 나간 물건에는 있는데
    저장소에는 없다.
    """
    result = _git("status", "--porcelain", "--", *SOURCE_DIRS, cwd=repo)
    return [line for line in result.stdout.splitlines() if line.strip()]


def source_gate_problems(repo: Path = REPO) -> list[str]:
    """빌드하기 전에 막는다. 빌드하고 막으면 몇 분을 버린다."""
    problems = upstream_problems(repo)

    left = source_dirty(repo)
    if left:
        problems.append(
            "우리 소스에 커밋 안 된 변경이 있다 - 그 트리로 만든 물건은 "
            "어느 저장소에도 안 남아 무엇이 나갔는지 되짚을 수 없다:"
        )
        problems += [f"  {line}" for line in left[:DIRTY_LINES]]
    return problems


# ── 산출물 검사 ────────────────────────────────────────────────────────────


def csproj_assembly_version(repo: Path) -> str | None:
    """빌드가 박는 버전. 조립 산출물의 csproj에서 읽는다.

    `upstream/`이 아니라 `build/`를 보는 이유는 **실제로 컴파일된 트리**가
    거기이기 때문이다. 조립을 안 돌린 상태면 `None`이고, 그러면 버전 대조가
    빠진다 - `dist`는 빌드 뒤에나 생기므로 이 검사가 도는 자리에서는
    `build/`가 있다.
    """
    csproj = repo / "build" / INTERNAL_NAME / f"{INTERNAL_NAME}.csproj"
    if not csproj.is_file():
        return None
    match = re.search(
        r"<AssemblyVersion>([^<]+)</AssemblyVersion>", csproj.read_text(encoding="utf-8")
    )
    return match.group(1) if match else None


def dist_layout_problems(dist: Path) -> list[str]:
    """받는 폴더에 있어야 할 것이 다 있고, 없어야 할 것이 없나.

    안내 문서가 여기 끼는 이유는 편의가 아니다. 설치의 첫 단계가 "문서를
    읽는 것"인데 그 문서가 저장소에만 있으면, 받는 사람은 무엇부터 눌러야
    하는지 알 방법이 없다.

    매니페스트 둘도 같은 이유로 여기 있다. 릴리스에 그 둘이 같이 안 올라가면
    자기 갱신과 커스텀 저장소가 통째로 죽는데, **받는 쪽은 그것을 오류가
    아니라 "새 판이 없다"로 읽는다.** 만드는 것은 `tools/release-manifest`고
    여기서는 나갈 자리에 있나만 본다.

    **자리가 둘로 갈린다.** 루트는 받는 사람에게 그대로 주는 넷이고,
    `release/`는 사람이 안 여는 것이다. 사용 안내가 "압축을 풀면 그 안에 넷이
    들어 있습니다"라고 세어 주는 그 폴더가 루트라, 거기 파일이 많으면 무엇을
    눌러야 하는지 헷갈린다. **개수를 세는 문장이 사용 안내에 있으므로 여기를
    늘리면 그 문장도 같이 고친다.**
    """
    if not dist.is_dir():
        # **잴 것이 없는 것을 통과로 세지 않는다.** 이 저장소에는 `dist`를
        # 만드는 절차가 아직 없어서, 지금은 반드시 여기로 온다.
        return [
            f"배포 폴더가 없다: {dist}. 산출물을 만드는 절차가 이 저장소에 아직 없다 - "
            f"조립은 `tools/assemble`이 `build/`까지 낸다"
        ]

    problems = []
    root_expected = {
        f"{INTERNAL_NAME}.zip",
        release_manifest.INSTALLER_NAME,
        GUIDE_NAME,
        KEYS_NAME,
    }
    # 노트는 **있어도 되지만 여기서 요구하지는 않는다.** 판마다 사람이 쓰는
    # 것이고 패킹은 그 전에 돈다 - 여기서 요구하면 그냥 빌드만 하려던 사람이
    # 매번 걸린다. 없으면 낼 수 없다는 것은 발행하는 자리가 못박는다.
    release_required = {*RELEASE_MANIFESTS}
    release_allowed = release_required | {RELEASE_NOTES_NAME}
    release = dist / RELEASE_DIR_NAME

    for name in sorted(root_expected):
        if not (dist / name).is_file():
            problems.append(f"산출물이 없다: {dist / name}")

    # 하위 폴더는 "배포물이 아닌 것"이 아니다. 이름만 빼고 따로 본다.
    known = root_expected | {RELEASE_DIR_NAME}
    extra = sorted(p.name for p in dist.iterdir() if p.name not in known)
    if extra:
        problems.append(f"dist 루트에 받는 사람이 안 쓰는 것이 있다: {', '.join(extra)}")

    if not release.is_dir():
        return problems + [f"릴리스용 폴더가 없다: {release}"]

    for name in sorted(release_required):
        if not (release / name).is_file():
            problems.append(f"산출물이 없다: {release / name}")

    extra = sorted(p.name for p in release.iterdir() if p.name not in release_allowed)
    if extra:
        problems.append(f"{RELEASE_DIR_NAME}에 배포물이 아닌 것이 있다: {', '.join(extra)}")

    return problems


def check_artifacts(dist: Path, repo: Path, needles: list[str]) -> list[str]:
    zip_path = dist / f"{INTERNAL_NAME}.zip"
    exe_path = dist / release_manifest.INSTALLER_NAME

    problems = dist_layout_problems(dist)
    if any(p.startswith(("산출물이 없다", "배포 폴더가 없다")) for p in problems):
        return problems

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        problems += zip_problems({i.filename: i.CRC for i in archive.infolist()})
        for name in names:
            found = personal_traces(archive.read(name), needles)
            if found:
                problems.append(f"압축의 {name}에 개인 흔적이 있다: {', '.join(found)}")
        if f"{INTERNAL_NAME}.json" in names:
            manifest = json.loads(archive.read(f"{INTERNAL_NAME}.json").decode("utf-8"))
            problems += manifest_problems(manifest, csproj_assembly_version(repo))

    found = personal_traces(exe_path.read_bytes(), needles)
    if found:
        problems.append(f"설치 프로그램 EXE에 개인 흔적이 있다: {', '.join(found)}")

    return problems


# ── 실물 검증 ──────────────────────────────────────────────────────────────


def installer_seed_containers(repo: Path) -> set[str]:
    """`KrProfile.ConfigSeed`가 만드는 최상위 컨테이너 이름들.

    **왜 소스에서 읽나**: 검사가 설치 프로그램보다 더 갖춰진 프로필을 만들면,
    설치 프로그램이 못 만드는 구조를 검사가 대신 만들어 주는 셈이 된다. 그러면
    실물에서만 터지고 검사는 조용히 통과한다. 실제로 그래서 **첫 설치가 반드시
    실패하는 결함**이 배포 직전까지 안 잡혔다 - 씨앗에는 `$type` 하나뿐인데
    여기서는 컨테이너 둘을 미리 채워 놓고 있었다.

    베끼지 않고 세는 쪽을 골랐다. 값까지 맞추면 그게 두 번째 사본이 된다.
    """
    source = (repo / "kr" / "Installer" / "KrProfile.cs").read_text(encoding="utf-8")
    match = re.search(r"private const string ConfigSeed\s*=(.*?);\n", source, re.DOTALL)
    if match is None:
        raise ValueError("KrProfile.cs에서 ConfigSeed를 못 찾았다")

    # C# 문자열 리터럴 조각을 이어 붙여 실제 JSON으로 되돌린다. 세는 것보다
    # 이쪽이 나은 이유는 **씨앗이 파싱되는지까지 여기서 걸리기 때문**이다 -
    # 안 그러면 그건 사용자 기계에서만 드러난다.
    pieces = re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))
    seed = json.loads("".join(pieces).replace('\\"', '"').replace("\\\\", "\\"))
    return {key for key, value in seed.items() if isinstance(value, dict)}


def _seed_dalamud(root: Path, *, marker: bool = True, assets: bool = True) -> None:
    """업데이터가 일을 마쳤을 때 남는 자취.

    **폴더 하나로는 모자란다.** 설치 프로그램이 준비 완료로 보는 조건이
    `addon\\Hooks` 존재였던 동안, 이 검사는 빈 폴더 하나로 통과하면서 실물에서
    업데이터가 **아직 쓰는 중인** 상태를 한 번도 안 태웠다(2026-08-20 실측:
    설치 프로그램이 07:57:41에 플러그인을 깔았는데 에셋은 07:57:46에 왔다).

    `marker`·`assets`를 끄면 그 중간 상태를 만들 수 있다. 정상 실행에서는 안
    생기는 조합이라 인위로만 만들어진다.
    """
    hooks = root / "addon" / "Hooks" / "15.0.0.0"
    hooks.mkdir(parents=True, exist_ok=True)
    if marker:
        # 이름 셋이 아니라 `Dalamud.KR.*.Patch.json` 패턴이 기준이다. 하나만
        # 만드는 것은 그 패턴이 개수에 안 기대는지도 같이 보기 때문이다.
        (hooks / "Dalamud.KR.Compatibility.Patch.json").write_text("{}", encoding="utf-8")
    if assets:
        (root / "dalamudAssets").mkdir(parents=True, exist_ok=True)
        (root / "dalamudAssets" / "asset.ver").write_text("437", encoding="utf-8")


def _seed_profile(root: Path) -> None:
    """설치 프로그램이 "Dalamud가 있다"고 볼 만큼만 갖춘 가짜 프로필.

    담는 것은 **설치 프로그램의 `KrProfile.ConfigSeed`가 담는 것과 같아야
    한다.** 여기가 더 갖춰져 있으면 첫 설치가 겪는 상태를 한 번도 안 태운다 -
    `installer_seed_containers`가 그걸 지킨다.
    """
    _seed_dalamud(root)
    (root / "dalamudConfig.json").write_text(
        json.dumps(
            {
                "$type": "Dalamud.Configuration.Internal.DalamudConfiguration, Dalamud",
                "DevPluginLoadLocations": {"$values": []},
                "ThirdRepoList": {"$values": []},
                "DefaultProfile": {"Plugins": {"$values": []}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def run_installer(
    exe: Path, root: Path, shortcut_dir: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["FF14ACC_KR_PROFILE"] = str(root)
    # 바로가기를 버리는 폴더로 돌린다. 안 그러면 검사를 돌릴 때마다 실제
    # 바탕화면에 바로가기가 하나씩 놓이고, 그러면 이 단계를 건너뛸 수밖에
    # 없어진다 - 아무 검사도 안 지나는 단계가 되는 것이 제일 나쁘다.
    if shortcut_dir is not None:
        env["FF14ACC_SHORTCUT_DIR"] = str(shortcut_dir)
    # .NET 감지는 지나가되 설치는 하지 않는다. 설치는 시스템 전역이라 버리는
    # 프로필로 격리가 안 되고, UAC 창이 뜨면 무인 실행이 거기서 멈춘다.
    # 감지 갈래를 지나는 것은 `dotnet_branch_ran`이 로그로 확인한다.
    env["FF14ACC_SKIP_DOTNET"] = "1"
    return subprocess.run(
        [str(exe), "--install", "--skip-vnavmesh"],
        capture_output=True,
        text=True,
        # 설치 프로그램은 `Console.WriteLine`으로 쓴다. 그건 콘솔 코드페이지지
        # utf-8이 아니라서, utf-8로 읽으면 **한국어가 전부 깨진 글자로 나온다.**
        # 실패했을 때 여기 담긴 출력이 유일한 단서인데 그게 안 읽혔다.
        encoding=locale.getpreferredencoding(False),
        errors="replace",
        env=env,
        timeout=300,
    )


#: `KrCheck.Run`이 준비 완료 판정을 내는 줄. `[OK ]`면 참, `[-- ]`면 거짓이다.
READY_LABEL = "dalamud ready"


def run_check(exe: Path, root: Path) -> subprocess.CompletedProcess[str]:
    """`--check`를 가짜 프로필에 대고 돌린다.

    `--bootstrap`이 아니라 `--check`인 것이 중요하다 - 이쪽은 읽기만 하고,
    `--bootstrap`은 **사용자 환경변수 DALAMUD_RUNTIME을 실제로 쓴다**
    (`kr/Installer/KrCheck.cs`의 `EnsureRuntimeVariable`). 검사가 기계 설정을
    건드리면 안 된다.
    """
    env = dict(os.environ)
    env["FF14ACC_KR_PROFILE"] = str(root)
    return subprocess.run(
        [str(exe), "--check"],
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors="replace",
        env=env,
        timeout=120,
    )


#: 바로가기를 되읽는 스크립트. `WScript.Shell`은 파이썬에서 못 부르므로
#: (pywin32가 이 저장소 의존성에 없다) 윈도가 기본으로 갖고 있는 `cscript`에
#: 넘긴다. 설치 프로그램이 바로가기를 **만드는** 데 쓰는 것과 같은 COM 개체다.
_READ_LNK_JS = """\
var shell = new ActiveXObject("WScript.Shell");
var link = shell.CreateShortcut(WScript.Arguments(0));
WScript.Echo("TargetPath=" + link.TargetPath);
WScript.Echo("Arguments=" + link.Arguments);
WScript.Echo("WorkingDirectory=" + link.WorkingDirectory);
"""


def read_shortcut(link: Path) -> dict[str, str]:
    """`.lnk`에 실제로 적힌 값. 못 읽으면 빈 사전.

    **파일이 생겼다는 것만으로 완료로 치지 않기 위해 있다.** 대상이 빈 채로
    저장된 바로가기도 파일로는 멀쩡히 존재한다.
    """
    workdir = Path(tempfile.mkdtemp(prefix="ff14acc-lnk-"))
    try:
        script = workdir / "readlnk.js"
        script.write_text(_READ_LNK_JS, encoding="utf-8")
        result = subprocess.run(
            ["cscript", "//nologo", str(script), str(link)],
            capture_output=True,
            text=True,
            encoding=locale.getpreferredencoding(False),
            errors="replace",
            timeout=60,
        )
        if result.returncode != 0:
            return {}
        pairs = (line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        return {key: value.strip() for key, value in pairs}
    except (OSError, subprocess.SubprocessError):
        return {}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def shortcut_problems(shortcut_dir: Path) -> list[str]:
    """설치 프로그램이 만든 플레이 바로가기가 실제로 실행 가능한 것을 가리키나."""
    links = list(shortcut_dir.glob("*.lnk"))
    if not links:
        return [f"플레이 바로가기를 안 만들었다: {shortcut_dir}"]
    if len(links) != 1:
        return [f"바로가기가 {len(links)}개다. 하나여야 한다: {shortcut_dir}"]

    values = read_shortcut(links[0])
    if not values:
        return [f"바로가기를 되읽지 못했다: {links[0]}"]

    target = Path(values.get("TargetPath", ""))
    if target.name != LAUNCHER_EXE:
        return [f"바로가기 대상이 런처가 아니다: {values.get('TargetPath', '(빈 값)')}"]
    if not target.is_file():
        return [f"바로가기가 없는 파일을 가리킨다: {target}"]
    if not values.get("WorkingDirectory"):
        return [f"바로가기에 작업 폴더가 없다: {links[0]}"]
    return []


def dotnet_branch_ran(stdout: str) -> bool:
    """설치 프로그램이 .NET 런타임 갈래를 지났나.

    **검사 밖에 남는 자리를 만들지 않기 위해 있다.** .NET은 없으면 게임
    안에서 모드가 아예 안 뜨므로 검사가 한 번도 안 태우는 자리에 두면 안 된다.

    재는 것은 판정이 아니라 **갈래를 지났다는 사실**이다. 이 머신에는 .NET
    10이 있어 "있음"으로 끝나고, "없음"과 종료 코드 판정은
    `tools/kr-setup/tests/test_dotnet_runtime.py`가 인위로 만들어 잰다.

    표식이 제품명인 것은 우연이 아니다. 세 언어 사전이 전부 `.NET {0}`으로
    시작하므로, 저장된 언어가 무엇이든 이 줄이 나온다.
    """
    return f".NET {kr_profile.DOTNET_REQUIRED_MAJOR}" in stdout


def dalamud_ready(stdout: str) -> bool:
    """`--check` 출력에서 준비 완료 판정만 골라낸다."""
    for line in stdout.splitlines():
        if READY_LABEL in line:
            return line.lstrip().startswith("[OK ]")
    raise ValueError(f"`--check` 출력에 `{READY_LABEL}` 줄이 없다:\n{stdout}")


def binding_detail(stdout: str, stderr: str = "") -> str:
    """asmref-check 출력에서 사람이 볼 줄만 남긴다.

    931건 중 걸린 것은 보통 한 줄이다. 전문을 그대로 뱉으면 그 한 줄이 묻힌다.
    아무 줄도 못 고르면 잘라서라도 원문을 보여 준다 - 조용히 "실패"만 남기는
    것이 제일 나쁘다.
    """
    picked = [line.strip() for line in stdout.splitlines() if "MISSING" in line or "ARITY" in line]
    if picked:
        return "; ".join(picked)
    return (stdout + stderr).strip()[-400:] or "(출력 없음)"


def kr_dalamud_dir() -> Path | None:
    """참조 어셈블리가 있는 KR Dalamud의 Hooks 폴더.

    규칙을 여기서 새로 만들지 않는다 - 이 저장소가 참조 자리를 부르는 이름은
    `DALAMUD_HOME`이고(`docs/dev/dalamud-refs.md`), 프로필 루트도 Hooks 폴더를
    고르는 규칙도 `kr_profile`이 정한다. `tools/pack`이 같은 값을 배포 절차에서
    쓰므로, 여기에 사본을 두면 둘이 갈린 채로 조용히 다른 참조를 잰다.
    """
    return kr_profile.dalamud_hooks_dir()


def dotnet_path() -> Path:
    """빌드에 쓸 .NET SDK. 개발 머신은 scoop, 러너는 PATH다.

    **개발 머신에서 PATH의 `dotnet`은 런타임뿐이다.** `C:\\Program Files\\dotnet`에
    SDK가 없어서 `dotnet build`가 "No .NET SDKs were found"로 죽고, scoop이 shim을
    안 깔아서 PATH로는 SDK에 닿을 길이 없다. 그래서 scoop 자리를 먼저 본다.

    **러너는 반대다.** `actions/setup-dotnet`이 깐 것이 PATH에 있고 그것이 SDK다.
    scoop 자리를 못 박아 두면 발행이 러너에서 돌 수가 없다 - 2026-09-04에 첫 CI
    발행이 정확히 그것으로 죽었다(`runneradmin`의 scoop을 찾았다).

    **SDK인지 짐작하지 않고 `--list-sdks`로 묻는다.** 이름이 같아도 런타임뿐인
    것이 이 머신에 실제로 있으므로, 있다는 것만으로 고르면 같은 사고가 반대
    방향으로 난다.
    """
    scoop = Path(os.environ.get("SCOOP", str(Path.home() / "scoop")))
    in_scoop = scoop / "apps" / "dotnet-sdk" / "current" / "dotnet.exe"
    if in_scoop.is_file() and _lists_sdks(in_scoop):
        return in_scoop

    found = shutil.which("dotnet")
    if found and _lists_sdks(Path(found)):
        return Path(found)

    # 못 찾았다. **scoop 자리를 그대로 돌려준다** - 부르는 쪽이 그 이름을 대고
    # 멈추므로, 개발 머신에서 무엇이 없는지가 메시지에 그대로 나온다.
    return in_scoop


def _lists_sdks(dotnet: Path) -> bool:
    """그 `dotnet`이 SDK를 하나라도 갖고 있나. 못 물어보면 False."""
    try:
        done = subprocess.run(
            [str(dotnet), "--list-sdks"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and bool(done.stdout.strip())


def check_kr_binding(
    dist: Path, repo: Path, kr_dalamud: str | None, dotnet: str | None
) -> list[str]:
    """압축 안의 DLL이 **KR이 깔아 둔** FFXIVClientStructs에 붙는가.

    KR Dalamud는 FFXIVClientStructs를 7.51로 낮춰 싣는다. 글로벌 참조로
    빌드된 DLL은 **적재는 되고 첫 호출에서 죽는다** - 게임 안에서만, 그것도
    특정 키를 눌러야 드러나는 고장이다. 참조를 어디서 얻는지는
    `docs/dev/dalamud-refs.md`가 갖는다.

    순서를 지키는 규율로는 못 막는다 - 산출물을 직접 재야 한다.
    """
    project = repo / "tools" / "asmref-check"
    if not project.is_dir():
        return [f"asmref-check가 없어 바인딩을 대조하지 못했다: {project}"]

    refdir = Path(kr_dalamud) if kr_dalamud else kr_dalamud_dir()
    if refdir is None or not refdir.is_dir():
        return ["KR Dalamud를 못 찾아 바인딩을 대조하지 못했다"]

    exe = Path(dotnet) if dotnet else dotnet_path()
    if not exe.is_file():
        return [f".NET SDK를 못 찾아 바인딩을 대조하지 못했다: {exe}"]

    workdir = Path(tempfile.mkdtemp(prefix="ff14acc-asmref-"))
    try:
        with zipfile.ZipFile(dist / f"{INTERNAL_NAME}.zip") as archive:
            archive.extract(f"{INTERNAL_NAME}.dll", workdir)

        result = subprocess.run(
            [
                str(exe),
                "run",
                "-c",
                "Release",
                "--project",
                str(project),
                "--",
                str(workdir / f"{INTERNAL_NAME}.dll"),
                str(refdir),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo),
            timeout=600,
        )
        if result.returncode != 0:
            return [
                "압축 안의 DLL이 KR FFXIVClientStructs에 안 붙는다. 글로벌 참조로 빌드된 "
                f"것이 섞였을 수 있다: {binding_detail(result.stdout, result.stderr)}"
            ]
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return []


def check_install_e2e(dist: Path) -> list[str]:
    """설치 프로그램을 버리는 프로필에 대고 실제로 돌려 보고 결과를 잰다."""
    exe = dist / release_manifest.INSTALLER_NAME
    if not exe.is_file():
        return [f"설치 프로그램이 없다: {exe}"]

    problems = []
    workdir = Path(tempfile.mkdtemp(prefix="ff14acc-e2e-"))
    try:
        root = workdir / "profile"
        root.mkdir()
        _seed_profile(root)

        # 옛 dev 설치가 남아 있는 머신을 흉내 낸다. 설치 프로그램이 이걸
        # 걷어내야 같은 모드가 두 번 적재되지 않는다.
        dev_dir = root / "devPlugins" / INTERNAL_NAME
        dev_dir.mkdir(parents=True)
        (dev_dir / f"{INTERNAL_NAME}.dll").write_bytes(b"stale")

        shortcut_dir = workdir / "shortcuts"
        shortcut_dir.mkdir()

        first = run_installer(exe, root, shortcut_dir)
        if first.returncode != 0:
            problems.append(
                f"설치 프로그램이 실패했다(코드 {first.returncode}):\n{first.stdout}{first.stderr}"
            )
            return problems

        problems += shortcut_problems(shortcut_dir)

        if not dotnet_branch_ran(first.stdout):
            problems.append(
                ".NET 런타임 갈래를 안 지났다. 없으면 게임 안에서 모드가 "
                "아예 안 뜨는데 검사가 그 자리를 한 번도 안 태운다"
            )

        plugin_root = root / "installedPlugins" / INTERNAL_NAME
        problems += installed_layout_problems(plugin_root)

        if dev_dir.exists():
            problems.append(f"dev 설치가 그대로 남았다: {dev_dir}")

        config = json.loads((root / "dalamudConfig.json").read_text(encoding="utf-8"))
        first_id = working_plugin_id(plugin_root)
        problems += config_problems(config, first_id, str(dev_dir / f"{INTERNAL_NAME}.dll"))

        # 두 번째 실행: 갱신 경로다. 신원이 바뀌면 프로필에 죽은 항목이 쌓인다.
        second = run_installer(exe, root, shortcut_dir)
        if second.returncode != 0:
            problems.append(f"두 번째 설치가 실패했다(코드 {second.returncode})")
        elif working_plugin_id(plugin_root) != first_id:
            problems.append("두 번 설치했더니 WorkingPluginId가 바뀌었다")

        problems += installed_layout_problems(plugin_root)
        # 두 번 깔아도 바로가기는 하나다. 이름을 바꿔 만들면 바탕화면에 매
        # 설치마다 하나씩 쌓인다.
        problems += shortcut_problems(shortcut_dir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return problems


def main(argv: list[str]) -> int:
    console.setup()
    parser = argparse.ArgumentParser(description="배포 산출물 위생·모양 검사")
    parser.add_argument("--dist", default=str(REPO / "dist"))
    parser.add_argument("--e2e", action="store_true", help="설치 프로그램을 실제로 돌려 본다")
    parser.add_argument("--kr-dalamud", help="KR Dalamud Hooks 폴더. 안 주면 DALAMUD_HOME")
    parser.add_argument("--dotnet", help=".NET SDK 경로. 안 주면 scoop 기본값")
    parser.add_argument(
        "--source-gate",
        action="store_true",
        help="소스가 커밋되어 있고 원본이 기록된 커밋에 있나만 본다. 빌드 전에 부르는 자리다",
    )
    args = parser.parse_args(argv[1:])

    if args.source_gate:
        problems = source_gate_problems()
        if problems:
            print("== 배포 게이트: 막힘 ==\n")
            for problem in problems:
                print(f"  {problem}")
            # 무엇을 해야 하는지는 줄마다 다르다. 여기서는 규칙만 되짚는다 -
            # 안 걸린 쪽까지 고치라고 말하면 엉뚱한 곳을 뒤지게 된다.
            print("\n  나가는 물건은 어느 저장소에든 남아 있는 트리에서만 만든다.")
            return 1
        print("== 배포 게이트: 소스가 깨끗함 ==")
        print(f"  {UPSTREAM_DIR}이 기록된 커밋에 있고 손댄 것이 없다")
        print(f"  커밋 안 된 변경이 없다: {', '.join(SOURCE_DIRS)}")
        return 0

    dist = Path(args.dist)
    problems = check_artifacts(dist, REPO, default_needles())
    if not problems:
        problems += check_kr_binding(dist, REPO, args.kr_dalamud, args.dotnet)
    if args.e2e:
        problems += check_install_e2e(dist)

    if problems:
        print("== 배포 검사: 확인 필요 ==\n")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("== 배포 검사: 통과 ==")
    print(f"  {dist}")
    if args.e2e:
        print("  설치 경로까지 실제로 돌려 봤다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
