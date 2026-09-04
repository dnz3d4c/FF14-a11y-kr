"""릴리스 매니페스트 생성기 테스트.

지키려는 것 둘.

- **값은 산출물에서 나온다.** 손으로 옮겨 적은 숫자는 낡는다. 그래서 여기서는
  "만든 것"이 아니라 **"산출물에서 다시 계산한 것과 같은가"**를 잰다
- **못 읽었으면 만들지 않는다.** 버전을 못 읽었는데 빈 값으로 내보내면
  설치 프로그램이 자기 갱신을 무한히 다시 권한다(`ParseVersionLoose` 주석)

읽는 쪽의 규칙이 근거다 - `replace/Installer/InstallerService.cs`의
`TrySelfUpdateAsync`(필드 셋)와 `ParseVersionLoose`(네 자리 채우기)다.
"""

import json
import os
import zipfile
from pathlib import Path

import pytest

import release_manifest as rm

VERSION = "5.88.0.0"

#: 주소를 박아 둔 C# 쪽. 조립이 `build/`로 옮기므로 커밋된 원본을 읽는다.
INSTALLER_SERVICE = (
    Path(rm.__file__).resolve().parents[2] / "replace" / "Installer" / "InstallerService.cs"
)

#: 이 모드가 전에 나가던 저장소. 자산은 이제 새 저장소에만 올라가므로
#: 우리가 만드는 `repo.json`에는 한 자리도 남으면 안 된다.
OLD_REPO = "ff14-ko-accessibility"

#: 원본이 쓰는 독일어 원문. 이게 그대로 나가면 한국 사용자가 못 읽는다.
GERMAN_DESCRIPTION = (
    "Macht FF14 für blinde Spieler zugänglich via NVDA/TOLK Integration, "
    "Audio-Navigation und vollständiger Tastatursteuerung."
)
GERMAN_PUNCHLINE = "FF14 für blinde Spieler via NVDA und Tastatur zugänglich machen."


def plugin_manifest(**overrides) -> dict:
    base = {
        "Author": "FF14 Accessibility Project",
        "Name": "FF14 Accessibility",
        "InternalName": "FF14Accessibility",
        "AssemblyVersion": VERSION,
        "Description": GERMAN_DESCRIPTION,
        "Punchline": GERMAN_PUNCHLINE,
        "ApplicableVersion": "any",
        "DalamudApiLevel": 15,
        "Tags": ["accessibility", "blind", "screenreader", "nvda"],
        "AcceptsFeedback": True,
    }
    base.update(overrides)
    return base


#: "안 넘겼다"와 "일부러 안 넣는다"를 가른다. `None`은 매니페스트 없는 압축을
#: 만드는 쪽이라 기본값으로 못 쓴다.
_DEFAULT = object()


def make_zip(dist: Path, manifest: object = _DEFAULT) -> Path:
    """배포 압축 하나. `manifest=None`이면 매니페스트를 안 넣는다."""
    path = dist / rm.ZIP_NAME
    content = plugin_manifest() if manifest is _DEFAULT else manifest
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{rm.INTERNAL_NAME}.dll", b"dll")
        if content is not None:
            archive.writestr(f"{rm.INTERNAL_NAME}.json", json.dumps(content))
    return path


def make_exe(dist: Path) -> Path:
    """버전 자원이 없는 가짜 EXE. 버전은 따로 넘겨 쓴다."""
    path = dist / rm.INSTALLER_NAME
    path.write_bytes(b"not a real PE")
    return path


def make_guide(dist: Path) -> Path:
    """받는 폴더에 같이 나가는 안내 문서."""
    path = dist / rm.GUIDE_NAME
    path.write_text("사용 안내", encoding="utf-8")
    return path


def make_keys(dist: Path) -> Path:
    """사용 안내 4장의 키만 모은 목록."""
    path = dist / rm.KEYS_NAME
    path.write_text("단축키 목록", encoding="utf-8")
    return path


def make_user_files(dist: Path) -> Path:
    """`dist` 루트에 받는 사람이 쓰는 넷을 만든다."""
    make_zip(dist)
    make_exe(dist)
    make_guide(dist)
    make_keys(dist)
    return dist


# ── 압축에서 읽기 ──────────────────────────────────────────────────────────


def test_압축에서_매니페스트를_읽는다(tmp_path):
    make_zip(tmp_path)
    assert rm.read_plugin_manifest(tmp_path / rm.ZIP_NAME)["AssemblyVersion"] == VERSION


def test_압축이_없으면_만들지_않는다(tmp_path):
    with pytest.raises(rm.ManifestError, match="압축이 없다"):
        rm.read_plugin_manifest(tmp_path / rm.ZIP_NAME)


def test_압축_안에_매니페스트가_없으면_만들지_않는다(tmp_path):
    make_zip(tmp_path, manifest=None)
    with pytest.raises(rm.ManifestError, match="매니페스트가 없다"):
        rm.read_plugin_manifest(tmp_path / rm.ZIP_NAME)


# ── 배포 폴더가 아예 없을 때 ───────────────────────────────────────────────
#
# **이 저장소에는 `dist`를 만드는 절차가 아직 없다.** 그래서 지금 이 도구를
# 부르면 반드시 여기로 온다. 조용히 0으로 끝나면 "만들 것이 없다"와
# "만들었다"가 같은 얼굴이 되므로, 무엇이 없는지 말하고 멈춰야 한다.


def test_배포_폴더가_없으면_그렇게_말한다(tmp_path):
    with pytest.raises(rm.ManifestError, match="배포 폴더가 없다"):
        rm.require_dist(tmp_path / "dist")


def test_배포_폴더가_있으면_통과한다(tmp_path):
    rm.require_dist(tmp_path)


# ── 못 읽은 것과 멀쩡한 것을 가른다 ────────────────────────────────────────
#
# **파싱이 실패했는데 아무 말도 안 하면, 릴리스가 멀쩡한 것과 검사가 못 읽은
# 것이 같은 얼굴이 된다.** 이 도구가 존재하는 이유가 그 부류를 가르는 것이라,
# 스택트레이스로 죽는 것은 검사를 안 한 것과 같다.


def test_압축이_깨졌으면_그렇게_말한다(tmp_path):
    (tmp_path / rm.ZIP_NAME).write_bytes(b"this is not a zip at all")
    with pytest.raises(rm.ManifestError, match="압축을 못 읽었다"):
        rm.read_plugin_manifest(tmp_path / rm.ZIP_NAME)


def test_압축_안_매니페스트가_JSON이_아니면_그렇게_말한다(tmp_path):
    path = tmp_path / rm.ZIP_NAME
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{rm.INTERNAL_NAME}.json", "{ 이건 JSON이 아니다")
    with pytest.raises(rm.ManifestError, match="못 읽었다"):
        rm.read_plugin_manifest(path)


def test_dist_매니페스트가_깨졌으면_그렇게_말한다(tmp_path):
    dist = make_dist(tmp_path)
    (rm.release_dir(dist) / rm.INSTALLER_MANIFEST_NAME).write_text("{ 깨졌다", encoding="utf-8")
    with pytest.raises(rm.ManifestError, match="못 읽었다"):
        rm.manifest_problems(dist, installer_version="1.1.0.0")


def test_릴리스_매니페스트가_깨졌으면_그렇게_말한다(tmp_path):
    path = tmp_path / rm.REPO_MANIFEST_NAME
    path.write_text("[{ 깨졌다", encoding="utf-8")
    with pytest.raises(rm.ManifestError, match="못 읽었다"):
        rm._read_repo_manifest(path)


def test_gh가_JSON이_아닌_것을_내면_그렇게_말한다():
    # gh가 오류를 0으로 내거나 출력이 잘리면 여기로 온다. 스택트레이스 대신
    # 무엇을 못 읽었는지 말해야 한다.
    with pytest.raises(rm.ManifestError, match="gh의 릴리스 정보"):
        rm._parse_object("not json", "gh의 릴리스 정보")


def test_JSON이지만_객체가_아니면_그렇게_말한다():
    with pytest.raises(rm.ManifestError, match="객체가 아니다"):
        rm._parse_object("[1, 2, 3]", "gh의 저장소 정보")


# ── repo.json ──────────────────────────────────────────────────────────────


def entry(**overrides) -> dict:
    return rm.build_repo_manifest(plugin_manifest(**overrides))[0]


def test_배열_안에_객체_하나다():
    made = rm.build_repo_manifest(plugin_manifest())
    assert isinstance(made, list)
    assert len(made) == 1


def test_값을_손으로_안_적고_압축에서_가져온다():
    made = entry(AssemblyVersion="9.9.9.9", DalamudApiLevel=16)
    assert made["AssemblyVersion"] == "9.9.9.9"
    assert made["DalamudApiLevel"] == 16
    assert made["InternalName"] == "FF14Accessibility"


def test_저장소_주소와_내려받기_링크는_우리_것이다():
    made = entry()
    assert made["RepoUrl"] == rm.DOC_REPO_URL
    for field in rm.DOWNLOAD_FIELDS:
        assert made[field] == rm.DOWNLOAD_URL
    # 원본 주소가 한 자리도 안 남아야 한다.
    assert "derbruedi" not in json.dumps(made)


def test_옛_저장소_주소가_한_자리도_안_남는다():
    """자산은 새 저장소에만 올라간다.

    옛 저장소는 이미 깐 사람을 위해 `repo.json` 한 파일만 남기는 창구이고,
    거기 놓이는 것도 **새 저장소의 자산을 가리키는** 내용이다(D-08). 우리가
    만드는 쪽에 옛 주소가 남으면 받는 쪽이 없는 자산을 받으러 간다.
    """
    assert OLD_REPO not in json.dumps(entry())


def test_독일어_설명을_한국어로_바꾼다():
    made = entry()
    assert "blinde Spieler" not in made["Description"]
    assert "파이널 판타지 14" in made["Description"]
    assert "파이널 판타지 14" in made["Punchline"]


def test_이미_한국어면_그대로_둔다():
    made = entry(Punchline="한국어 한 줄 소개입니다.")
    assert made["Punchline"] == "한국어 한 줄 소개입니다."


def test_모르는_외국어_문장은_조용히_안_내보낸다():
    # 원본이 문구를 고치면 표가 빗나간다. 그때 독일어가 그대로 나가면
    # 아무도 모른 채 배포된다.
    with pytest.raises(rm.ManifestError, match="옮길 문장"):
        entry(Description="Ein ganz neuer Satz vom Upstream.")


def test_있어야_할_필드가_비면_만들지_않는다():
    with pytest.raises(rm.ManifestError, match="AssemblyVersion"):
        entry(AssemblyVersion="")


def test_원본_필드_순서를_따른다():
    assert list(entry()) == list(rm.FIELD_ORDER)


# ── 주소 셋이 각자 무엇을 가리키나 ─────────────────────────────────────────
#
# 전에는 주소 하나에서 넷이 파생했다. 그러면 발행 대상만 옮기고 싶을 때
# 문서 주소까지 같이 움직인다. 지금은 셋이 따로 있고, **기계가 대조하는
# 하나만** C# 쪽과 글자까지 같아야 한다.


def test_내려받기_주소가_설치_프로그램과_글자까지_같다():
    """Dalamud가 `InstalledFromUrl`을 `==`로 대조한다.

    한 글자만 달라도 우리 모드가 목록에서 사라진다. 그래서 두 벌이 있는
    것을 두고 "맞겠지"로 넘기지 않고 소스를 읽어 대조한다.
    """
    text = INSTALLER_SERVICE.read_text(encoding="utf-8")
    assert f'"{rm.REPO_JSON_URL}"' in text, (
        f"설치 프로그램의 KrRepoUrl과 갈렸다: {rm.REPO_JSON_URL}"
    )


def test_릴리스_페이지_주소도_같은_저장소다():
    """사람이 설치 프로그램을 손으로 받는 자리다. 자산이 있는 저장소여야 한다."""
    text = INSTALLER_SERVICE.read_text(encoding="utf-8")
    assert f'"{rm.DOWNLOAD_REPO_URL}/releases/latest"' in text


def test_발행_대상은_gh가_받는_꼴이다():
    """`gh --repo`에 그대로 넘기므로 주소가 아니라 `owner/name`이다."""
    assert not rm.GH_REPO.startswith("http")
    assert rm.GH_REPO == rm.DOWNLOAD_REPO_URL.removeprefix("https://github.com/")


def test_문서_주소는_저장소에_실제로_있는_파일을_가리킨다():
    """지어낸 경로를 적으면 받는 사람이 404를 본다."""
    repo = Path(rm.__file__).resolve().parents[2]
    for url, path in (
        (rm.GUIDE_DOC_URL, repo / "docs" / "korean" / "README.ko.md"),
        (rm.KEYS_DOC_URL, repo / "docs" / "korean" / "keys.md"),
    ):
        assert path.is_file(), f"{url}이 가리키는 파일이 저장소에 없다: {path}"


# ── installer.json ─────────────────────────────────────────────────────────


def test_설치_프로그램_매니페스트는_세_필드다(tmp_path):
    exe = make_exe(tmp_path)
    made = rm.build_installer_manifest(exe, "1.1.0.0")
    assert set(made) == {"InstallerVersion", "AssetName", "Sha256"}
    assert made["AssetName"] == rm.INSTALLER_NAME


def test_해시는_실제_파일에서_계산한다(tmp_path):
    import hashlib

    exe = make_exe(tmp_path)
    made = rm.build_installer_manifest(exe, "1.1.0.0")
    assert made["Sha256"].lower() == hashlib.sha256(exe.read_bytes()).hexdigest()


def test_버전이_세_자리면_네_자리로_채운다(tmp_path):
    # 읽는 쪽(`ParseVersionLoose`)이 네 자리로 채워 비교한다. 우리가 세 자리로
    # 내보내면 같은 판을 새 판으로 읽어 갱신을 무한히 다시 권한다.
    made = rm.build_installer_manifest(make_exe(tmp_path), "1.1.0")
    assert made["InstallerVersion"] == "1.1.0.0"


def test_버전_정규화():
    assert rm.normalize_version("1.1.0.0") == "1.1.0.0"
    assert rm.normalize_version("1.1.0") == "1.1.0.0"
    assert rm.normalize_version("1.1") == "1.1.0.0"
    assert rm.normalize_version("v1.1.0") == "1.1.0.0"


def test_읽는_쪽이_못_읽을_버전은_거른다():
    # 마디가 다섯이면 `ParseVersionLoose`가 null을 돌려주고, 그러면 비교가
    # 문자열 같음으로 떨어져 갱신을 계속 권한다.
    for bad in ("1.1.0.0.1", "1.1.0-kr.1", ""):
        with pytest.raises(rm.ManifestError, match="버전"):
            rm.normalize_version(bad)


def test_EXE에서_버전을_못_읽으면_만들지_않는다(tmp_path):
    with pytest.raises(rm.ManifestError, match="버전 자원"):
        rm.file_version(make_exe(tmp_path))


def test_EXE가_없으면_만들지_않는다(tmp_path):
    with pytest.raises(rm.ManifestError, match="설치 프로그램이 없다"):
        rm.file_version(tmp_path / rm.INSTALLER_NAME)


@pytest.mark.skipif(
    not (Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "notepad.exe").is_file(),
    reason="윈도 표준 EXE가 없다",
)
def test_진짜_PE에서는_버전을_읽는다():
    """ctypes 배선이 실제로 도는가. 값이 아니라 모양만 본다."""
    exe = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "notepad.exe"
    version = rm.file_version(exe)
    assert len(version.split(".")) == 4
    assert all(part.isdigit() for part in version.split("."))


# ── 다시 재기 ──────────────────────────────────────────────────────────────
#
# 만든 뒤에 산출물만 다시 빌드하면 매니페스트가 조용히 낡는다. 그 상태가
# 제일 나쁘다 - 설치 프로그램이 해시가 안 맞는다며 갱신을 거부하는데,
# 그건 사용자 화면에서만 보인다.


def make_dist(tmp_path) -> Path:
    make_user_files(tmp_path)
    rm.write_manifests(tmp_path, installer_version="1.1.0.0")
    return tmp_path


def test_갓_만든_것은_통과한다(tmp_path):
    dist = make_dist(tmp_path)
    assert rm.manifest_problems(dist, installer_version="1.1.0.0") == []


def test_해시가_실제_파일과_다르면_잡는다(tmp_path):
    dist = make_dist(tmp_path)
    path = rm.release_dir(dist) / rm.INSTALLER_MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["Sha256"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")

    problems = rm.manifest_problems(dist, installer_version="1.1.0.0")
    assert any("Sha256" in p for p in problems)


def test_압축을_다시_빌드해_버전이_갈리면_잡는다(tmp_path):
    dist = make_dist(tmp_path)
    make_zip(dist, plugin_manifest(AssemblyVersion="5.89.0.0"))

    problems = rm.manifest_problems(dist, installer_version="1.1.0.0")
    assert any("AssemblyVersion" in p for p in problems)


def test_매니페스트가_아예_없으면_잡는다(tmp_path):
    make_zip(tmp_path)
    make_exe(tmp_path)
    problems = rm.manifest_problems(tmp_path, installer_version="1.1.0.0")
    assert any(rm.REPO_MANIFEST_NAME in p for p in problems)
    assert any(rm.INSTALLER_MANIFEST_NAME in p for p in problems)


def test_루트에는_사용자가_쓸_것만_남는다(tmp_path):
    """`dist` 루트는 **사용자에게 그대로 줄 수 있는 폴더**다.

    사용 안내가 "압축을 풀면 그 안에 넷이 들어 있습니다"라고 세어 주는 그
    폴더라, 기계만 읽는 파일이 섞이면 사용자가 무엇을 눌러야 하는지 헷갈린다.
    """
    dist = make_dist(tmp_path)
    assert sorted(p.name for p in dist.iterdir()) == sorted([*rm.USER_FILES, rm.RELEASE_DIR_NAME])


def test_매니페스트는_release_폴더에_만든다(tmp_path):
    dist = make_dist(tmp_path)
    assert sorted(p.name for p in rm.release_dir(dist).iterdir()) == sorted(
        [rm.REPO_MANIFEST_NAME, rm.INSTALLER_MANIFEST_NAME]
    )


def test_release_폴더가_없으면_만든다(tmp_path):
    make_user_files(tmp_path)
    assert not rm.release_dir(tmp_path).exists()
    rm.write_manifests(tmp_path, installer_version="1.1.0.0")
    assert (rm.release_dir(tmp_path) / rm.REPO_MANIFEST_NAME).is_file()


# ── 받는 사람이 받는 것 ────────────────────────────────────────────────────


def test_문서는_자산이_아니라_주소로_준다():
    """**파일로 안 주고 주소로 준다.**

    `.md`를 받아 열면 그려 주는 프로그램이 없는 한 제목 구조가 없어서
    스크린리더 제목 탐색이 안 된다.
    """
    assert not any(name.endswith(".md") for name in rm.RELEASE_ASSETS), rm.RELEASE_ASSETS
    for url in (rm.GUIDE_DOC_URL, rm.KEYS_DOC_URL):
        assert url.startswith(f"{rm.DOC_REPO_URL}/blob/master/"), url
        # 판마다 값이 달라지면 나가 있는 노트를 소급해 고칠 때 값이 갈린다.
        assert "/blob/v" not in url, url


def test_자산_목록은_넷이다():
    # 개수를 세는 것은 **자산이 조용히 사라지는 것**을 막으려는 것이다. 늘릴
    # 때는 올리는 쪽이 실제로 그것을 올리는지 같이 본다 - 목록에만 넣고 안
    # 올리면 `--release`가 매번 빨개진다.
    assert len(rm.RELEASE_ASSETS) == 4


def test_설치_프로그램이_자산_목록의_첫째다():
    """받는 사람이 누르는 것이다. 순서가 릴리스 페이지의 노출 순서는 아니지만,
    이 목록에서 사람이 받는 것을 맨 앞에 두는 규약을 지킨다.
    """
    assert rm.RELEASE_ASSETS[0] == rm.INSTALLER_NAME


# ── KR 표시 ────────────────────────────────────────────────────────────────
#
# 버전만 보면 원본 모드와 헷갈린다. 태그에는 못 넣는다 - `ChoosePluginSourceAsync`가
# 태그에서 버전을 뽑아 비교하는데 `5.88.0.0-kr`은 `ParseVersionLoose`가 못 읽어서
# 문자열 비교로 떨어지고, 그러면 최신을 깔고 있어도 실행할 때마다 다시 받는다.
# 그래서 **사람이 읽는 자리에만** 넣는다.


def test_플러그인_목록_이름에_한국_서버가_드러난다():
    made = entry()
    assert made["Name"] == rm.PLUGIN_DISPLAY_NAME
    assert "한국" in made["Name"]


def test_내부_이름은_안_건드린다():
    """설치된 폴더 이름이자 갱신 대조 키다."""
    assert entry()["InternalName"] == "FF14Accessibility"


def test_표시_이름이_설치_프로그램_창_제목과_같은_말을_쓴다():
    # 사용자가 실제로 듣는 이름이 `Loc.cs`의 `FF14 접근성 모드 ... 한국 서버`다.
    assert "FF14 접근성 모드" in rm.PLUGIN_DISPLAY_NAME


def test_경로를_두_곳에_안_박는다(tmp_path):
    """만드는 자리와 다시 재는 자리가 같은 상수에서 나온다."""
    dist = make_dist(tmp_path)
    # `release_dir`이 가리키는 곳을 비우면 `--check`가 없다고 말해야 한다.
    (rm.release_dir(dist) / rm.REPO_MANIFEST_NAME).unlink()
    problems = rm.manifest_problems(dist, installer_version="1.1.0.0")
    assert any(rm.REPO_MANIFEST_NAME in p for p in problems)


# ── 릴리스를 다시 재기 ─────────────────────────────────────────────────────
#
# `dist`가 완벽해도 업로드에서 하나 빠지면 그대로 나간다. 그 실패는 오류가
# 아니라 **침묵**이다 - 받는 쪽은 "새 판이 없다"로 읽는다. 그래서 여기서는
# `dist`를 안 보고 **릴리스에서 받아 다시 계산한다.**
#
# 아직 릴리스가 없어 실물로는 못 태운다. 갈래는 전부 픽스처로 돈다.

TAG = "v5.88.0.0"


def release_facts(tmp_path, **overrides) -> rm.ReleaseFacts:
    """아무 문제 없는 릴리스. 테스트마다 한 자리씩 망가뜨린다."""
    exe = tmp_path / rm.INSTALLER_NAME
    exe.write_bytes(b"released installer")

    installer = {
        "InstallerVersion": "1.1.0.0",
        "AssetName": rm.INSTALLER_NAME,
        "Sha256": rm.sha256(exe),
    }
    base = {
        "tag": TAG,
        "asset_names": rm.RELEASE_ASSETS,
        "repo_manifest": rm.build_repo_manifest(plugin_manifest()),
        "installer_manifest": installer,
        "plugin_manifest": plugin_manifest(),
        "exe": exe,
        "exe_version": "1.1.0.0",
        "link_status": {
            rm.DOWNLOAD_URL: 200,
            rm.REPO_JSON_URL: 200,
            rm.dotnet_runtime_url(): 200,
        },
        "is_draft": False,
        "is_private": False,
    }
    base.update(overrides)
    return rm.ReleaseFacts(**base)


def test_멀쩡한_릴리스는_통과한다(tmp_path):
    assert rm.release_problems(release_facts(tmp_path)) == []


# 1. 자산 넷이 이름까지 정확히 있나


def test_자산이_넷이_아니면_잡는다(tmp_path):
    남은것 = tuple(n for n in rm.RELEASE_ASSETS if n != rm.INSTALLER_NAME)
    problems = rm.release_problems(release_facts(tmp_path, asset_names=남은것))
    assert any(rm.INSTALLER_NAME in p for p in problems)


def test_대소문자만_다른_자산은_그렇게_말한다(tmp_path):
    # 설치 프로그램은 `OrdinalIgnoreCase`로 찾아 넘어가는데, 내려받기 주소는
    # 이름을 그대로 쓴다. 한쪽만 되는 상태라 따로 말해 줘야 한다.
    바뀐것 = tuple("repo.JSON" if n == rm.REPO_MANIFEST_NAME else n for n in rm.RELEASE_ASSETS)
    problems = rm.release_problems(release_facts(tmp_path, asset_names=바뀐것))
    assert any("대소문자" in p for p in problems)


# 2. 릴리스 EXE를 내려받아 다시 계산한 해시와 같나


def test_해시가_릴리스_EXE와_다르면_잡는다(tmp_path):
    facts = release_facts(tmp_path)
    facts.installer_manifest["Sha256"] = "0" * 64
    problems = rm.release_problems(facts)
    assert any("Sha256" in p for p in problems)


def test_업로드가_끊긴_EXE를_잡는다(tmp_path):
    """올라간 파일이 `dist`의 그것과 다르면 해시가 안 맞는다."""
    facts = release_facts(tmp_path)
    facts.exe.write_bytes(b"released installer (truncated)")
    assert any("Sha256" in p for p in rm.release_problems(facts))


# 3. AssetName이 실재하는 자산을 가리키나


def test_AssetName이_없는_자산을_가리키면_잡는다(tmp_path):
    facts = release_facts(tmp_path)
    facts.installer_manifest["AssetName"] = "FF14AccessibilityInstaller.exe"
    problems = rm.release_problems(facts)
    assert any("AssetName" in p for p in problems)


# 4. 다운로드 링크가 릴리스 자산과 맞고 실제로 200을 내나


def test_링크가_200이_아니면_잡는다(tmp_path):
    facts = release_facts(tmp_path, link_status={rm.DOWNLOAD_URL: 404, rm.REPO_JSON_URL: 200})
    problems = rm.release_problems(facts)
    assert any("404" in p for p in problems)


def test_저장소가_비공개면_repo_json_주소에서_드러난다(tmp_path):
    # Dalamud가 이 주소를 그대로 박아 쓴다(`InstallerService.cs`의 `KrRepoUrl`).
    facts = release_facts(tmp_path, link_status={rm.DOWNLOAD_URL: 200, rm.REPO_JSON_URL: 404})
    problems = rm.release_problems(facts)
    assert any(rm.REPO_JSON_URL in p for p in problems)


def test_링크를_못_열었으면_이유를_말한다(tmp_path):
    facts = release_facts(
        tmp_path, link_status={rm.DOWNLOAD_URL: "이름을 못 찾았다", rm.REPO_JSON_URL: 200}
    )
    assert any("이름을 못 찾았다" in p for p in rm.release_problems(facts))


def test_닷넷_주소가_죽으면_잡는다(tmp_path):
    """우리 자산이 아니지만 첫 설치가 여기 매여 있다.

    죽으면 갓 받은 사람이 런타임 없이 끝나고, 게임 안에서 모드가 안 뜬다.
    """
    facts = release_facts(
        tmp_path,
        link_status={rm.DOWNLOAD_URL: 200, rm.REPO_JSON_URL: 200, rm.dotnet_runtime_url(): 404},
    )
    assert any(rm.dotnet_runtime_url() in p for p in rm.release_problems(facts))


def test_닷넷_주소를_아예_안_재면_잡는다(tmp_path):
    """검사에서 주소가 빠지는 것이 404보다 나쁘다 - 조용히 통과한다."""
    facts = release_facts(tmp_path, link_status={rm.DOWNLOAD_URL: 200, rm.REPO_JSON_URL: 200})
    assert any(rm.dotnet_runtime_url() in p for p in rm.release_problems(facts))


def test_링크_셋이_갈리면_잡는다(tmp_path):
    facts = release_facts(tmp_path)
    facts.repo_manifest[0]["DownloadLinkTesting"] = "https://example.invalid/x.zip"
    assert any("DownloadLinkTesting" in p for p in rm.release_problems(facts))


def test_링크가_가리키는_파일이_릴리스에_없으면_잡는다(tmp_path):
    facts = release_facts(tmp_path)
    바뀐주소 = f"{rm.DOWNLOAD_REPO_URL}/releases/latest/download/latest.zip"
    for field in rm.DOWNLOAD_FIELDS:
        facts.repo_manifest[0][field] = 바뀐주소
    problems = rm.release_problems(
        facts._replace(link_status={바뀐주소: 200, rm.REPO_JSON_URL: 200})
    )
    assert any("latest.zip" in p for p in problems)


# 5. InstallerVersion이 네 마디이고 EXE의 PE 버전과 같나


def test_버전이_세_마디로_올라갔으면_잡는다(tmp_path):
    facts = release_facts(tmp_path)
    facts.installer_manifest["InstallerVersion"] = "1.1.0"
    problems = rm.release_problems(facts)
    assert any("네 마디" in p for p in problems)


def test_버전이_릴리스_EXE와_다르면_잡는다(tmp_path):
    facts = release_facts(tmp_path)
    facts.installer_manifest["InstallerVersion"] = "1.2.0.0"
    problems = rm.release_problems(facts)
    assert any("PE 버전" in p for p in problems)


# 6. 태그가 플러그인 버전과 맞나


def test_태그가_플러그인_버전과_갈리면_잡는다(tmp_path):
    # `ChoosePluginSourceAsync`가 태그에서 v를 떼어 설치된 버전과 비교한다.
    # 태그가 낮으면 새 판이 올라가 있어도 "이미 최신"으로 읽는다.
    problems = rm.release_problems(release_facts(tmp_path, tag="v5.87.0.0"))
    assert any("태그" in p for p in problems)


def test_v가_없는_태그도_같은_것으로_본다(tmp_path):
    assert rm.release_problems(release_facts(tmp_path, tag="5.88.0.0")) == []


# 7. 초안이 아닌가
#
# 내는 사람 화면에서는 멀쩡해 보이는데 받는 쪽에서는 아예 안 보인다.
# 이 도구가 존재하는 이유와 정확히 같은 부류다.


def test_초안이면_잡는다(tmp_path):
    problems = rm.release_problems(release_facts(tmp_path, is_draft=True))
    assert any("초안" in p for p in problems)


# 8. 올라간 repo.json에 한국어가 있나
#
# `GERMAN_TO_KOREAN`은 **만드는 쪽**을 막는다. 이건 **올라간 쪽**을 막는다.
# 손으로 고친 repo.json을 올렸거나 옛 판이 올라갔으면 여기서만 걸린다.


def test_올라간_설명이_독일어면_잡는다(tmp_path):
    facts = release_facts(tmp_path)
    facts.repo_manifest[0]["Description"] = GERMAN_DESCRIPTION
    problems = rm.release_problems(facts)
    assert any("Description" in p and "한국어" in p for p in problems)


def test_올라간_한줄소개가_독일어면_잡는다(tmp_path):
    facts = release_facts(tmp_path)
    facts.repo_manifest[0]["Punchline"] = GERMAN_PUNCHLINE
    assert any("Punchline" in p for p in rm.release_problems(facts))


# 9. repo.json의 버전과 릴리스 zip 안 매니페스트의 버전이 같나
#
# 어긋나면 Dalamud가 받아 놓고 같은 판을 다시 받는다.


def test_repo_json과_압축_안_버전이_갈리면_잡는다(tmp_path):
    facts = release_facts(tmp_path, plugin_manifest=plugin_manifest(AssemblyVersion="5.87.0.0"))
    problems = rm.release_problems(facts)
    assert any("압축 안" in p for p in problems)


# ── 404를 왜 나는지까지 말하나 ─────────────────────────────────────────────
#
# "404"만 말하면 받는 사람은 원인을 모른다. `gh`는 인증을 갖고 있어서
# 비공개 저장소도 멀쩡히 보고, 그래서 자산 목록만으로는 절대 안 드러난다.


def _막힌주소(tmp_path, **overrides):
    return release_facts(
        tmp_path, link_status={rm.DOWNLOAD_URL: 404, rm.REPO_JSON_URL: 404}, **overrides
    )


def test_비공개면_비공개라고_말한다(tmp_path):
    problems = rm.release_problems(_막힌주소(tmp_path, is_private=True))
    assert any("비공개" in p for p in problems)
    assert not any("초안" in p for p in problems)


def test_초안이면_초안_때문이라고_말한다(tmp_path):
    problems = rm.release_problems(_막힌주소(tmp_path, is_draft=True))
    assert any("초안" in p and "404" in p for p in problems)


def test_자산이_없어서_난_404는_한_번만_말한다(tmp_path):
    """한 고장을 세 줄로 말하면 그중 아무것도 안 읽힌다."""
    남은것 = tuple(n for n in rm.RELEASE_ASSETS if n != rm.ZIP_NAME)
    problems = rm.release_problems(_막힌주소(tmp_path, asset_names=남은것))

    assert any("릴리스에 자산이 없다" in p and rm.ZIP_NAME in p for p in problems)
    # 같은 까닭을 주소 줄에서 되풀이하지 않는다. 원인을 못 찾았다고도 안 한다.
    assert not any(rm.DOWNLOAD_URL in p for p in problems)
    assert not any("비공개" in p for p in problems)


def test_원인을_못_찾으면_모른다고_말한다(tmp_path):
    # 공개이고 초안도 아니고 자산도 다 있는데 404다. 지어내지 않는다.
    problems = rm.release_problems(_막힌주소(tmp_path))
    assert any("원인" in p for p in problems)


# ── 상수가 두 번 정의되지 않았나 ───────────────────────────────────────────
#
# 편집이 겹치면 같은 상수가 두 번 정의되고, **파이썬은 뒤엣것을 조용히
# 쓴다.** ruff도 모듈 수준 재할당은 `F811`로 안 잡는다. 눈으로 보는 대신
# 여기서 잡는다.


def test_모듈_수준_상수가_한_번씩만_정의된다():
    import ast
    import collections

    source = Path(rm.__file__).read_text(encoding="utf-8")
    defined: collections.Counter[str] = collections.Counter()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            defined.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined.update([node.target.id])

    두번이상 = {name: count for name, count in defined.items() if count > 1}
    assert not 두번이상, f"같은 이름을 두 번 정의했다(뒤엣것이 조용히 이긴다): {두번이상}"


# ── 릴리스가 없을 때 ───────────────────────────────────────────────────────


def test_릴리스가_없으면_그렇게_말한다():
    error = rm.gh_failure(TAG, "release not found", 1)
    assert "릴리스가 없다" in str(error)
    assert TAG in str(error)
    assert rm.GH_REPO in str(error)


def test_그밖의_gh_실패는_원문을_붙인다():
    error = rm.gh_failure(TAG, "HTTP 401: Bad credentials", 1)
    assert "Bad credentials" in str(error)
    assert "릴리스가 없다" not in str(error)


def test_저장소를_못_찾은_것을_릴리스_탓으로_돌리지_않는다():
    # 같은 `gh` 실패라도 릴리스를 찾을 때와 저장소를 찾을 때가 다른 말을
    # 해야 한다. 안 그러면 원인을 엉뚱한 데서 찾는다.
    error = rm.gh_failure(rm.GH_REPO, "not found", 1, missing=f"저장소를 못 찾았다: {rm.GH_REPO}")
    assert "저장소를 못 찾았다" in str(error)
    assert "릴리스가 없다" not in str(error)


# ── 버전이 올라갔나 ────────────────────────────────────────────────────────
#
# **산출물이 바뀌었는데 버전이 그대로면 갱신이 침묵한다.** `IsNewer`가 거짓을
# 돌려주므로 오류도 안 나고, 받는 쪽은 "새 판이 없다"로 읽는다. 그래서
# **올리기 전에** 이 검사를 세웠다.


def gh_listing(*tags: str) -> str:
    """`gh release list --json tagName`이 내는 꼴. 목록 순서가 곧 최신 순이다."""
    return json.dumps([{"tagName": tag} for tag in tags])


def test_우리_판이_아닌_릴리스는_이전_판으로_안_본다(monkeypatch):
    # 이 저장소에는 참조 어셈블리 릴리스(`dalamud-kr-*`)가 같이 있다. 그것에는
    # 매니페스트가 없어서, 이전 판으로 집으면 받다가 죽는다.
    monkeypatch.setattr(rm, "_gh", lambda *a, **k: gh_listing("dalamud-kr-15.0.3.2", "v5.95.0.0"))
    assert rm.latest_release_tag() == "v5.95.0.0"


def test_우리_판이_여럿이면_목록에서_앞선_것을_고른다(monkeypatch):
    monkeypatch.setattr(rm, "_gh", lambda *a, **k: gh_listing("v5.96.0.0", "v5.95.0.0"))
    assert rm.latest_release_tag() == "v5.96.0.0"


def test_우리_판이_하나도_없으면_첫_판이다(monkeypatch):
    # 릴리스는 있는데 전부 남의 것인 상태다. **첫 판을 낼 때 실제로 여기 섰다.**
    monkeypatch.setattr(rm, "_gh", lambda *a, **k: gh_listing("dalamud-kr-15.0.3.2"))
    assert rm.latest_release_tag() is None


def test_릴리스가_아예_없어도_첫_판이다(monkeypatch):
    monkeypatch.setattr(rm, "_gh", lambda *a, **k: "[]")
    assert rm.latest_release_tag() is None


def test_태그_이름이_없으면_첫_판으로_넘기지_않는다(monkeypatch):
    # gh의 출력이 바뀐 것을 "우리 판이 없다"로 읽으면 검사가 조용히 죽는다.
    monkeypatch.setattr(rm, "_gh", lambda *a, **k: json.dumps([{"name": "v5.95.0.0"}]))
    with pytest.raises(rm.ManifestError, match="태그 이름이 없다"):
        rm.latest_release_tag()


def dist_versions(plugin: str = "5.88.0.0", installer: str = "1.1.1.0") -> dict[str, str]:
    """매니페스트 이름을 키로 하는 버전 둘. 이름은 상수에서 나온다."""
    return {rm.REPO_MANIFEST_NAME: plugin, rm.INSTALLER_MANIFEST_NAME: installer}


def bump_facts(**overrides) -> rm.BumpFacts:
    """이미 나간 것과 지금 낼 것이 같은 상태. 여기서 한 자리씩 옮긴다."""
    base: dict = {"latest_tag": TAG, "released": dist_versions(), "local": dist_versions()}
    base.update(overrides)
    return rm.BumpFacts(**base)


def test_둘_다_같으면_막는다():
    assert any("똑같다" in p for p in rm.bump_problems(bump_facts()))


def test_플러그인만_올라도_통과한다():
    assert rm.bump_problems(bump_facts(local=dist_versions(plugin="5.88.0.1"))) == []


def test_설치_프로그램만_올라도_통과한다():
    assert rm.bump_problems(bump_facts(local=dist_versions(installer="1.1.1.1"))) == []


def test_버전이_내려가면_막는다():
    problems = rm.bump_problems(bump_facts(local=dist_versions(plugin="5.87.0.0")))
    assert any("낮다" in p for p in problems)


def test_하나가_올라도_다른_하나가_내려가면_막는다():
    """올린 것이 내린 것을 덮지 않는다. 내려간 쪽은 그 자체로 사고다."""
    facts = bump_facts(local=dist_versions(plugin="5.89.0.0", installer="1.1.0.0"))
    assert any("낮다" in p for p in rm.bump_problems(facts))


def test_릴리스가_하나도_없으면_통과한다():
    # 첫 릴리스다. **비교할 상대가 없는 것과 안 올린 것은 다르다.**
    assert rm.bump_problems(bump_facts(latest_tag=None, released={})) == []


def test_릴리스에서_버전을_못_읽으면_막는다():
    # 못 읽은 것을 통과로 세면 검사가 조용히 죽는다. 이 도구가 존재하는
    # 이유와 정확히 반대되는 자리다.
    assert any("못 읽었다" in p for p in rm.bump_problems(bump_facts(released={})))


def test_dist에서_버전을_못_읽으면_막는다():
    assert any("못 읽었다" in p for p in rm.bump_problems(bump_facts(local={})))


def test_읽는_쪽이_못_읽는_버전은_비교하지_않고_말한다():
    # 마디가 다섯이면 `ParseVersionLoose`가 null을 준다. 그런 값끼리 크기를
    # 재면 통과든 실패든 근거가 없다.
    facts = bump_facts(local=dist_versions(plugin="5.88.0.0.1"))
    assert any("비교할 수 없다" in p for p in rm.bump_problems(facts))


def test_매니페스트_둘에서_버전만_뽑는다(tmp_path):
    """받은 것과 만든 것을 **같은 함수로** 읽는다. 두 벌이 되면 갈린다."""
    dist = make_dist(tmp_path)
    found = rm.manifest_versions(rm.release_dir(dist))
    assert found == {rm.REPO_MANIFEST_NAME: VERSION, rm.INSTALLER_MANIFEST_NAME: "1.1.0.0"}


def test_매니페스트가_없으면_그_자리를_안_만든다(tmp_path):
    assert rm.manifest_versions(tmp_path) == {}
