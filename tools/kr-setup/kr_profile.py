"""KR Dalamud 프로필 루트가 어디인지 정하는 한 곳.

## 무엇을 막나

**우리가 플러그인을 넣은 곳과 업데이터가 보는 곳이 갈리는 것.**

갈려도 오류가 안 난다. 업데이터는 자기 설정대로 다른 폴더를 보고, 거기가
비어 있으면 **빈 프로필을 새로 만들어 주입한다.** 게임은 뜨고 Dalamud도 뜨고
플러그인만 조용히 빠진다 - "아무 일도 안 일어난다"의 원인은 늘 경로 중
하나다.

## 왜 박아 두면 안 되나

이 값을 아는 자리가 둘이다.

- `kr/Installer/KrProfile.cs` - 우리가 남에게 주는 EXE에 들어간다
- 이 파일 - 검사 도구들이 프로필을 찾을 때 쓴다

둘이 서로 맞는지는 `tests/test_kr_profile.py`가 소스를 읽어 대조한다. 업데이터의
**실제** 설정과 맞는지는 아무도 안 봐 주므로, 박아 두는 대신 읽는다.

## 권위는 업데이터의 설정이다

`%APPDATA%\\KrDalamudUpdater\\settings.json`의 `ProfileRoot`. 이건 우리가
찾아낸 내부 값이 아니라 **문서에 적힌 사용자 설정**이다 - `README-KR.txt`:
"사용자 설정은 %APPDATA%\\KrDalamudUpdater\\settings.json에 보관됩니다".
업데이터가 `settings.json.bak`을 남기며 자기가 다시 쓰므로 살아 있는 값이다.

**읽기만 한다.** 남의 설정 파일을 우리가 쓰지 않는다. 읽는 것은 거기 해당하지
않고, 오히려 **박아 두는 쪽이 결합이 더 세다**: 박아 두면 "그쪽 기본값이 안
바뀐다"와 "사용자가 안 고친다" 둘 다에 걸어야 하는데, 읽으면 전자만 남고
그마저 폴백이 받는다.

## 순서

1. `FF14ACC_KR_PROFILE` - 우리 탈출구. 옮긴 프로필을 가리키거나, 아무것도
   없는 상태의 분기를 이미 다 있는 머신에서 돌려 보려고 쓴다
2. 업데이터 설정의 `ProfileRoot` (환경변수 펼친 뒤)
3. `%APPDATA%\\XIVLauncherKR` - 업데이터의 기본값과 같은 값

2번이 없거나 못 읽거나 못 쓸 값이면 조용히 3번으로 간다. **남의 파일이
깨졌다고 우리가 죽지 않는다.**

사용법:
    uv run python tools/kr-setup/kr_profile.py        # 루트를 찍는다
    uv run python tools/kr-setup/kr_profile.py --why  # 어디서 나왔는지도
"""

from __future__ import annotations

import json
import ntpath
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: 우리 탈출구. 설치 프로그램(`kr/Installer/KrProfile.cs`)과 같은 이름이어야 한다.
ROOT_OVERRIDE_VARIABLE = "FF14ACC_KR_PROFILE"

#: 업데이터가 사용자 설정을 두는 곳. `README-KR.txt`에 적힌 자리다.
UPDATER_SETTINGS_DIR = "KrDalamudUpdater"
UPDATER_SETTINGS_NAME = "settings.json"
PROFILE_ROOT_KEY = "ProfileRoot"

#: 업데이터의 기본값과 같은 폴더 이름. 우리가 지은 이름이 아니다.
DEFAULT_FOLDER = "XIVLauncherKR"

#: 업데이터를 받아 오는 곳. 태그를 박지 않는다 - 최신 릴리스를 묻는다.
UPDATER_RELEASE_API = "https://api.github.com/repos/MiqoKR/kr-dalamud-updater/releases/latest"

#: 자산 둘 중 어느 쪽인가. `Payload`는 업데이터가 자기 갱신에 쓰는 것이라
#: 실행 파일이 없다. 이름으로 가르는 표지는 이 낱말 하나다.
UPDATER_ASSET_MARKER = "Portable"

#: 어디에 푸나. `%LOCALAPPDATA%` 밑이라 관리자 권한이 필요 없고, 업데이터
#: 자신의 `README-KR.txt`가 요구하는 "쓰기 가능한 일반 폴더"를 만족한다.
UPDATER_INSTALL_FOLDER = "KR-Dalamud-Updater"
UPDATER_APP_FOLDER = "app"
UPDATER_EXE_NAME = "Dalamud.Updater.exe"


# ── .NET 데스크톱 런타임 ───────────────────────────────────────────────────
#
# 아래 넷은 `kr/Installer/KrProfile.cs`와 같은 값이어야 하고, 갈라지면
# `tests/test_dotnet_runtime.py`가 실패한다. 없으면 게임 안에서 CLR이
# 조용히 안 뜬다 - 오류가 아니라 침묵이라 사용자가 원인을 못 짚는다.

#: 받는 곳. 채널 고정(`10.0`)이라 패치 판이 올라도 이 주소가 안 낡는다.
#: 실측으로 301을 거쳐 `builds.dotnet.microsoft.com`의 실제 판본으로 간다.
DOTNET_DOWNLOAD_URL = "https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-x64.exe"

#: 몇 판이 있어야 하나. 플러그인이 `net10.0-windows`로 빌드된다.
DOTNET_REQUIRED_MAJOR = 10


# ── 던전 경로 파일 ────────────────────────────────────────────────────────
#
# 경로 파일을 받아 오는 일은 원본이 `DungeonPathDownloadService`와 설치
# 프로그램 양쪽에 직접 넣었고 그 값을 자기 소스에 갖는다. 우리가 두 벌로 들고
# 있으면 어느 쪽이 진짜인지 갈리므로 **원본을 그대로 따른다**(D-06).

#: 모드가 읽는 폴더 이름. `DungeonRouteService.FolderName`과 같아야 하고,
#: 갈라지면 `tests/test_kr_profile.py`가 실패한다. 대조 대상이 설치
#: 프로그램이 아니라 모드 쪽이다.
DUNGEON_PATHS_FOLDER = "DungeonPaths"

#: 무인 설치 인자. Microsoft Learn "Install .NET on Windows"의 규격이다.
DOTNET_INSTALL_ARGS = "/install /quiet /norestart"

#: 데스크톱 런타임이 판본별 폴더를 두는 자리. `<dotnetRoot>\shared\` 밑이다.
DOTNET_DESKTOP_SHARED = "Microsoft.WindowsDesktop.App"

#: 설치 프로그램이 남긴 종료 코드를 옮긴 값. C#의 `DotnetInstallResult`와 같다.
DOTNET_INSTALLED = "installed"
DOTNET_REBOOT_REQUIRED = "reboot_required"
DOTNET_CANCELLED = "cancelled"
DOTNET_FAILED = "failed"


def has_desktop_runtime(dotnet_root: str, major: int = DOTNET_REQUIRED_MAJOR) -> bool:
    """`dotnet_root`에 그 판의 데스크톱 런타임이 깔려 있나.

    `dotnet --list-runtimes`를 부르지 않는다. 이 PC의 시스템 dotnet에는 SDK가
    없어 프로세스 호출이 불안정하고(`dotnet --version`이 exit 155), 업데이터
    부트스트랩도 같은 디렉토리 방식을 쓴다.

    경로를 인자로 받는 것이 요점이다 - 그래야 "없음" 갈래를 빈 디렉토리로
    실증할 수 있다. 이 머신에는 10이 있어서 그 갈래가 자연 발생하지 않는다.
    """
    shared = Path(dotnet_root) / "shared" / DOTNET_DESKTOP_SHARED
    try:
        entries = list(shared.iterdir())
    except OSError:
        return False  # 폴더가 없으면 런타임도 없다

    for entry in entries:
        if not entry.is_dir():
            continue
        head = entry.name.split(".", 1)[0]
        if head.isdigit() and int(head) == major:
            return True
    return False


def dotnet_install_result(exit_code: int) -> str:
    """설치 프로그램의 종료 코드를 판정으로 옮긴다.

    `3010`을 실패로 읽으면 **깔린 런타임을 두고 실패했다고 말한다.** 재부팅이
    필요할 뿐 설치는 끝난 상태다.

    `1223`은 종료 코드가 아니라 UAC를 껐을 때의 `Win32Exception` 오류 번호다.
    프로세스가 시작조차 안 되니 코드가 없는데, 두 경로의 판정이 갈리면 안
    되므로 같은 표에서 받는다.
    """
    if exit_code == 0:
        return DOTNET_INSTALLED
    if exit_code == 3010:
        return DOTNET_REBOOT_REQUIRED
    if exit_code == 1223:
        return DOTNET_CANCELLED
    return DOTNET_FAILED


# ── 업데이터가 이미 떠 있나 ────────────────────────────────────────────────

#: 업데이터 프로세스 이름의 **접두사**. 정확히 일치로 물으면 안 된다.
#:
#: `Dalamud.Updater.exe`는 부트스트랩이고, 그것이
#: `versions\<판>\Dalamud.Updater.Gui.exe`를 띄우고 물러난다. 2026-08-21
#: 실측에서 떠 있던 것은 `Dalamud.Updater.Gui` 하나뿐이었다.
UPDATER_PROCESS_PREFIX = "Dalamud.Updater"


def is_updater_process(name: str) -> bool:
    """프로세스 이름이 KR 달라무드 업데이터의 것인가.

    묶은 바로가기가 이 판정으로 **두 번 띄우는 것**을 막는다. 같은 게임에
    인젝터가 둘 붙으면 그 상태를 사용자가 귀로 알아챌 방법이 없다.
    """
    return name.lower().startswith(UPDATER_PROCESS_PREFIX.lower())


def _appdata() -> str:
    return os.environ.get("APPDATA", "")


def settings_path() -> Path:
    return Path(_appdata()) / UPDATER_SETTINGS_DIR / UPDATER_SETTINGS_NAME


def default_root() -> str:
    return str(Path(_appdata()) / DEFAULT_FOLDER)


def usable(candidate: str) -> bool:
    """업데이터가 거부하는 값은 우리도 안 쓴다.

    거부는 둘뿐이다 - `%APPDATA%` 자신과 드라이브 루트. 둘 다 프로필 루트로
    삼으면 남의 폴더를 통째로 프로필처럼 다루게 된다.
    """
    if not candidate or not candidate.strip():
        return False

    normalized = ntpath.normcase(ntpath.normpath(candidate))
    if normalized == ntpath.normcase(ntpath.normpath(_appdata())):
        return False

    return ntpath.dirname(normalized) != normalized


def from_settings() -> str | None:
    """업데이터 설정의 `ProfileRoot`. 못 읽으면 None.

    깨진 JSON·없는 키·빈 값·거부 대상은 전부 None이다. 남의 파일이라
    우리가 고쳐 주지 않고 그냥 안 쓴다.
    """
    path = settings_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if not isinstance(raw, dict):
        return None

    value = raw.get(PROFILE_ROOT_KEY)
    if not isinstance(value, str):
        return None

    # 업데이터가 실제로 `%APPDATA%\XIVLauncherKR` 모양으로 저장한다.
    expanded = os.path.expandvars(value).strip()
    return expanded if usable(expanded) else None


def resolve_root() -> str:
    override = os.environ.get(ROOT_OVERRIDE_VARIABLE, "").strip()
    if override:
        return override
    return from_settings() or default_root()


def source() -> str:
    """루트가 어디서 나왔는지. 진단용 - 갈렸을 때 어느 쪽인지 알아야 한다."""
    if os.environ.get(ROOT_OVERRIDE_VARIABLE, "").strip():
        return f"환경변수 {ROOT_OVERRIDE_VARIABLE}"
    if from_settings():
        return f"업데이터 설정 {settings_path()}"
    return "기본값 (업데이터 설정 없음/못 씀)"


# ── Dalamud Hooks 폴더 ────────────────────────────────────────────────────
#
# 참조 어셈블리가 있는 자리다. 프로필 루트에 매여 있으므로 그것을 정하는 이
# 파일이 같이 갖는다. **부르는 곳이 둘 이상이다** - `tools/pack-check`가 배포
# 검사에서 참조로 쓰고 `tools/pack`이 그 값을 검사에 넘긴다. 사본을 만들면
# 둘이 갈리고, 갈려도 오류가 안 난다.

#: 이 저장소가 참조 자리를 부르는 이름(`docs/dev/dalamud-refs.md`).
DALAMUD_HOME_VARIABLE = "DALAMUD_HOME"

#: 이름이 버전인 폴더들 사이에 섞여 있는 수동 구성 잔재. 개발 빌드라 참조로 안 쓴다.
HOOKS_DEV_NAME = "dev"


def dalamud_hooks_dir() -> Path | None:
    """참조 어셈블리가 있는 KR Dalamud의 Hooks 폴더. 못 찾으면 None.

    폴더 이름이 버전이라 업데이터가 갱신할 때마다 바뀐다. 이름 오름차순의
    마지막이 최신이고, 그걸 손으로 고치지 않으려고 여기서 고른다.
    """
    home = os.environ.get(DALAMUD_HOME_VARIABLE, "").strip()
    if home:
        return Path(home)

    hooks = Path(resolve_root()) / "addon" / "Hooks"
    if not hooks.is_dir():
        return None
    versions = sorted(d for d in hooks.iterdir() if d.is_dir() and d.name != HOOKS_DEV_NAME)
    return versions[-1] if versions else None


def updater_install_root() -> str:
    """업데이터를 두는 폴더."""
    return str(Path(os.environ.get("LOCALAPPDATA", "")) / UPDATER_INSTALL_FOLDER)


def updater_extract_dir() -> str:
    """배포 zip을 푸는 폴더.

    zip이 평평해서(루트에 `Dalamud.Updater.exe`·`README-KR.txt`·
    `UpdaterReleaseConfig.json`) 여기에 통째로 푼다. `UpdaterReleaseConfig.json`은
    exe 옆에 있어야 자기 갱신이 도므로 셋을 갈라 놓으면 안 된다.
    """
    return str(Path(updater_install_root()) / UPDATER_APP_FOLDER)


def updater_path() -> str:
    """업데이터 실행 파일. 설치 프로그램이 "있나 없나"를 이 경로로 묻는다."""
    return str(Path(updater_extract_dir()) / UPDATER_EXE_NAME)


def pick_updater_asset(assets) -> str | None:
    """릴리스 자산 목록에서 받을 zip의 URL. 못 고르면 None.

    이름에 `Portable`이 들어간 zip만 받는다. 같은 릴리스에 올라오는
    `Payload` zip은 업데이터가 자기를 갱신할 때 쓰는 것이라 실행 파일이
    없고, 그걸 받으면 **압축은 멀쩡히 풀리고 exe만 없다.**
    """
    if not isinstance(assets, list):
        return None

    marker = UPDATER_ASSET_MARKER.lower()
    for entry in assets:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        url = entry.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        lowered = name.lower()
        if marker in lowered and lowered.endswith(".zip"):
            return url
    return None


def main(argv: list[str]) -> int:
    print(resolve_root())
    if "--why" in argv:
        print(f"  출처: {source()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
