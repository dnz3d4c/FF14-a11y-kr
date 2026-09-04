"""업데이터를 어디서 받아 어디에 푸는가.

막는 사고는 둘이다.

**틀린 자산을 받는 것.** 릴리스에 zip이 둘 올라온다 - `Portable`(우리가
원하는 것)과 `Payload`(업데이터가 자기 갱신에 쓰는 것). 이름만 보고 첫
zip을 집으면 실행 파일이 없는 쪽을 받고, 압축은 멀쩡히 풀리므로 오류도 안
난다. 사용자는 `Dalamud.Updater.exe`가 없는 폴더를 얻는다.

**푸는 자리가 갈리는 것.** 설치 프로그램이 푸는 곳과 `KrProfile.UpdaterPath`가
찾는 곳이 다르면, 받아 놓고도 "아직 없다"고 말한다.
"""

import ntpath

import pytest

import kr_profile

#: 설치 프로그램이 같은 규칙을 갖는 자리. 조립이 이 파일을 `build/`로 옮기므로
#: 커밋된 원본인 이쪽을 읽는다 - `build/`는 조립을 돌려야 생긴다.
INSTALLER_SOURCE = kr_profile.REPO / "kr" / "Installer" / "KrProfile.cs"


def asset(name):
    return {
        "name": name,
        "browser_download_url": f"https://example.invalid/{name}",
    }


# 2026-08-19 실측: `updater-v0.5.0`이 실제로 내놓는 두 자산.
REAL_ASSETS = [
    asset("KR-Dalamud-Updater-0.5.0-Portable.zip"),
    asset("KR-Dalamud-Updater-Payload.zip"),
]


# --- 어느 자산을 받나 ------------------------------------------------------


def test_실제_릴리스에서_Portable을_고른다():
    url = kr_profile.pick_updater_asset(REAL_ASSETS)
    assert url == "https://example.invalid/KR-Dalamud-Updater-0.5.0-Portable.zip"


def test_Payload가_먼저_와도_Portable을_고른다():
    url = kr_profile.pick_updater_asset(list(reversed(REAL_ASSETS)))
    assert url and "Portable" in url


def test_Payload만_있으면_안_고른다():
    """받아 봐야 실행 파일이 없다. 못 찾았다고 말하는 쪽이 맞다."""
    assert kr_profile.pick_updater_asset([asset("KR-Dalamud-Updater-Payload.zip")]) is None


def test_대소문자를_안_따진다():
    url = kr_profile.pick_updater_asset([asset("kr-dalamud-updater-PORTABLE.ZIP")])
    assert url is not None


def test_zip이_아니면_안_고른다():
    assert kr_profile.pick_updater_asset([asset("Portable-notes.txt")]) is None


def test_자산이_없으면_None():
    assert kr_profile.pick_updater_asset([]) is None


@pytest.mark.parametrize("broken", [None, [{}], [{"name": "Portable.zip"}]])
def test_모양이_깨져도_안_죽는다(broken):
    """남의 API가 모양을 바꿔도 우리가 예외로 죽지 않는다."""
    assert kr_profile.pick_updater_asset(broken) is None


# --- 어디에 푸나 -----------------------------------------------------------


def test_푸는_자리가_찾는_자리와_같다(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    exe = kr_profile.updater_path()
    assert exe.startswith(kr_profile.updater_install_root())
    assert exe.endswith(kr_profile.UPDATER_EXE_NAME)


def test_zip은_app_폴더에_푼다(tmp_path, monkeypatch):
    """배포 zip은 평평하다 - 루트에 exe와 설정 파일이 그냥 들어 있다.

    2026-08-19 실측 내용물: `Dalamud.Updater.exe`, `README-KR.txt`,
    `UpdaterReleaseConfig.json`. 그래서 exe가 있는 폴더에 통째로 풀어야
    한다. 한 단계 위에 풀면 `app\\` 아래를 찾는 쪽이 못 본다.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert ntpath.dirname(kr_profile.updater_path()) == kr_profile.updater_extract_dir()


# --- 갈라지지 않았나 - 지금 저장소 -----------------------------------------


def test_설치_프로그램이_같은_규칙을_적어_뒀다():
    """C# 쪽은 여기서 못 부른다(단일 EXE). 규칙이 갈라지지 않았나만 본다."""
    text = INSTALLER_SOURCE.read_text(encoding="utf-8")
    for token in (
        kr_profile.UPDATER_RELEASE_API,
        kr_profile.UPDATER_ASSET_MARKER,
        kr_profile.UPDATER_INSTALL_FOLDER,
        kr_profile.UPDATER_APP_FOLDER,
        kr_profile.UPDATER_EXE_NAME,
    ):
        assert token in text, f"설치 프로그램에 `{token}`이 없다 - 두 규칙이 갈라졌다"
