""".NET 데스크톱 런타임이 있는가, 그리고 깔았을 때 무슨 일이 있었나.

막는 사고는 하나다 — **런타임이 없는데 설치가 성공했다고 말하는 것.**

없으면 `DALAMUD_RUNTIME`이 빈 채로 남고, 게임은 뜨는데 게임 안에서 CLR만
조용히 안 뜬다. `KrProfile.cs` 머리 주석이 세 실패 중 **"고약한 것"**이라고
따로 적어 둔 자리다: 아무 데서도 오류로 알려 주지 않는다.

C# 쪽은 여기서 못 부른다(단일 파일 EXE). `pick_updater_asset`과 같은
관례로 판정 로직만 미러링하고, 갈라지지 않았는지는 소스를 읽어 대조한다.
"""

import json

import pytest

import kr_profile

#: 설치 프로그램이 같은 값을 갖는 자리. 조립이 이 파일을 `build/`로 옮기므로
#: 커밋된 원본인 이쪽을 읽는다 - `build/`는 조립을 돌려야 생긴다.
INSTALLER_SOURCE = kr_profile.REPO / "kr" / "Installer" / "KrProfile.cs"

# --- 있는가 ----------------------------------------------------------------


def make_runtime(root, *versions):
    """`<dotnetRoot>\\shared\\Microsoft.WindowsDesktop.App\\<판본>`을 만든다.

    실측 모양 그대로다 - 이 PC의 `C:\\Program Files\\dotnet` 밑에
    `10.0.11`·`9.0.19`·`8.0.30` 셋이 나란히 있다.
    """
    shared = root / "shared" / kr_profile.DOTNET_DESKTOP_SHARED
    for version in versions:
        (shared / version).mkdir(parents=True)
    return root


def test_같은_판이_있으면_참(tmp_path):
    make_runtime(tmp_path, "10.0.11")
    assert kr_profile.has_desktop_runtime(str(tmp_path), 10)


def test_판이_여럿이어도_하나만_맞으면_참(tmp_path):
    # 실측 그대로. 옛 판을 지우지 않는 것이 .NET의 정상 상태다.
    make_runtime(tmp_path, "8.0.30", "9.0.19", "10.0.11")
    assert kr_profile.has_desktop_runtime(str(tmp_path), 10)


def test_낮은_판만_있으면_거짓(tmp_path):
    """**이 갈래가 자연 발생하지 않아 인위로 만든다.** 이 PC에는 10이 있다.

    9만 있는 머신에서 참을 돌려주면 설치를 건너뛰고, 그 결과는 게임 안의
    침묵이다.
    """
    make_runtime(tmp_path, "8.0.30", "9.0.19")
    assert not kr_profile.has_desktop_runtime(str(tmp_path), 10)


def test_shared가_비면_거짓(tmp_path):
    make_runtime(tmp_path)
    assert not kr_profile.has_desktop_runtime(str(tmp_path), 10)


def test_dotnet_폴더가_없으면_거짓(tmp_path):
    """.NET을 한 번도 안 깐 머신. 첫 사용자가 실제로 여기 있다."""
    assert not kr_profile.has_desktop_runtime(str(tmp_path / "없는폴더"), 10)


def test_판_이름이_숫자가_아니면_안_센다(tmp_path):
    """`x64` 같은 곁 폴더가 섞여도 판본으로 읽지 않는다."""
    make_runtime(tmp_path, "x64", "latest")
    assert not kr_profile.has_desktop_runtime(str(tmp_path), 10)


def test_첫_마디만_본다(tmp_path):
    """`10.0.11`의 `10`을 본다. 패치 판이 올라도 판정이 안 바뀌어야 한다."""
    make_runtime(tmp_path, "10.5.42")
    assert kr_profile.has_desktop_runtime(str(tmp_path), 10)


# --- 깔았더니 무슨 일이 있었나 ---------------------------------------------
#
# 설치 프로그램이 돌려주는 코드는 Microsoft Learn "Install .NET on Windows"가
# 적은 규격이다. 0과 3010만 성공이고, **3010을 실패로 읽으면 이미 깔린
# 런타임을 두고 실패했다고 말한다.**


def test_0은_설치됨():
    assert kr_profile.dotnet_install_result(0) == kr_profile.DOTNET_INSTALLED


def test_3010은_재부팅_필요():
    """깔리긴 깔렸다. 실패로 세면 안 된다."""
    assert kr_profile.dotnet_install_result(3010) == kr_profile.DOTNET_REBOOT_REQUIRED


def test_1223은_사용자_취소():
    """UAC를 사용자가 껐다. 오류로 겁주지 않고 안내만 한다."""
    assert kr_profile.dotnet_install_result(1223) == kr_profile.DOTNET_CANCELLED


@pytest.mark.parametrize("code", [1602, 1603, 5, -1])
def test_나머지는_실패(code):
    assert kr_profile.dotnet_install_result(code) == kr_profile.DOTNET_FAILED


# --- 갈라지지 않았나 - 지금 저장소 -----------------------------------------


def test_설치_프로그램이_같은_코드를_읽는다():
    """C#의 `ClassifyInstallCode`와 이쪽 판정표가 같은 숫자를 쓰는가."""
    text = INSTALLER_SOURCE.read_text(encoding="utf-8")
    for token in (
        kr_profile.DOTNET_DOWNLOAD_URL,
        kr_profile.DOTNET_INSTALL_ARGS,
        kr_profile.DOTNET_DESKTOP_SHARED,
        str(kr_profile.DOTNET_REQUIRED_MAJOR),
        "3010",
        "1223",
    ):
        assert token in text, f"설치 프로그램에 `{token}`이 없다 - 두 판정이 갈라졌다"


# --- 업데이터가 이미 떠 있나 -----------------------------------------------
#
# 막는 사고는 **업데이터를 두 번 띄우는 것**이다. 묶은 바로가기가 매번 새
# 업데이터를 열면 같은 게임에 인젝터가 둘 붙는다.
#
# 이름이 하나가 아니다. 우리가 실행하는 것은 `Dalamud.Updater.exe`인데, 그건
# 부트스트랩이라 `versions\<판>\Dalamud.Updater.Gui.exe`를 띄우고 물러난다.
# 2026-08-21 실측에서 떠 있던 것은 `Dalamud.Updater.Gui` 하나뿐이었다 -
# 정확히 일치하는 이름으로 물으면 **떠 있는 업데이터를 못 알아본다.**


def test_실제로_뜨는_GUI_이름을_잡는다():
    assert kr_profile.is_updater_process("Dalamud.Updater.Gui")


def test_부트스트랩_이름도_잡는다():
    assert kr_profile.is_updater_process("Dalamud.Updater")


def test_대소문자를_안_따진다():
    assert kr_profile.is_updater_process("dalamud.updater.gui")


@pytest.mark.parametrize("name", ["Dalamud", "ffxiv_dx11", "Dalamud.Injector", ""])
def test_남의_프로세스는_안_잡는다(name):
    assert not kr_profile.is_updater_process(name)


def test_설치_프로그램이_같은_접두사를_쓴다():
    text = INSTALLER_SOURCE.read_text(encoding="utf-8")
    assert kr_profile.UPDATER_PROCESS_PREFIX in text, "설치 프로그램과 접두사가 갈라졌다"


# --- 업데이터가 달라무드를 알아서 붙이는가 ---------------------------------
#
# 이 테스트가 받치는 것은 코드가 아니라 **문서**다. `docs/korean/README.ko.md`가
# "모드는 이 다음에 자동으로 붙습니다. 업데이터 창에서 따로 누를 버튼은
# 없습니다"라고 적고 있고, 그게 참인 근거는 업데이터의 자동 적용 설정이다.
# 그 값이 거짓이 되면 그날 문서가 틀린다.
#
# **업데이터 자신의 `README-KR.txt`는 근거로 안 쓴다.** 그 파일은 아직 "게임을
# 실행한 뒤 달라무드 적용을 누릅니다"라고 적혀 있어서 실물과 반대다. 재는
# 것은 설정값이다.

needs_updater_settings = pytest.mark.skipif(
    not kr_profile.settings_path().is_file(),
    reason="업데이터 설정이 없다 - 업데이터를 아직 안 깔았다",
)


@needs_updater_settings
def test_업데이터가_자동_적용으로_설정되어_있다():
    raw = json.loads(kr_profile.settings_path().read_text(encoding="utf-8"))
    assert raw.get("AutoApply") is True, (
        "업데이터의 AutoApply가 참이 아니다 - 사용 안내가 누를 버튼이 없다고 적은 것이 틀리게 된다"
    )
    assert raw.get("AutoStart") is True, (
        "업데이터의 AutoStart가 참이 아니다 - 묶은 바로가기가 업데이터를 "
        "띄워도 감시를 시작하지 않는다"
    )
