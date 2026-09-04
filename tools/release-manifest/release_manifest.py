"""릴리스에 올릴 것을 `dist`의 산출물에서 만든다.

`dist` 루트에 이미 있는 것을 읽어 **`dist\\release\\`에 둘을 낸다.** 루트는
받는 사람에게 그대로 줄 수 있는 폴더로 두고, 사람이 안 여는 것은 거기로 내린다.

1. **`dist\\release\\repo.json`** - Dalamud 커스텀 저장소 매니페스트. 사용자가
   저장소 주소를 등록해 두면 Dalamud가 이걸 보고 새 판을 알아서 받는다. 형식은
   원본 `repo.json`을 본뜨고, 값은 **압축 안의 `FF14Accessibility.json`에서
   읽는다** - 저장소 주소와 내려받기 링크, 그리고 목록에 그려지는 이름만 우리
   것으로 갈아 끼운다
2. **`dist\\release\\installer.json`** - 설치 프로그램 자기 갱신용. 읽는 쪽은
   `replace/Installer/InstallerService.cs`의 `TrySelfUpdateAsync`이고, 거기서
   쓰는 필드는 `InstallerVersion`·`AssetName`·`Sha256` 셋이다

**`dist`를 만드는 절차는 이 저장소에 아직 없다.** 조립(`tools/assemble`)이
`build/`까지 내고, 거기서 배포 산출물을 뽑는 단계는 다음에 세운다. 그때까지
이 도구는 **무엇이 없어서 못 하는지만 말한다** - 조용히 0으로 끝나면 "만들
것이 없다"와 "만들었다"가 같은 얼굴이 된다.

**값을 손으로 안 적는 것이 이 도구의 존재 이유다.** 손으로 옮겨 적은 숫자는
낡고, 릴리스 매니페스트는 그중에서도 낡은 것이 제일 늦게 드러나는 자리다 -
해시가 어긋나면 설치 프로그램이 갱신을 거부하는데, 그건 받는 사람 화면에서만
보인다.

재는 갈래가 둘 더 있고, **보는 곳이 다르다.**

- `--check`는 `dist`를 잰다. 산출물만 다시 빌드하고 매니페스트를 안 고친
  상태를 잡는다
- `--release <태그>`는 **`dist`를 안 보고 릴리스에서 도로 받아** 잰다.
  `dist`가 완벽해도 업로드에서 하나 빠지면 그대로 나가는데, 그 실패는
  오류가 아니라 침묵이다

사용법:
    uv run python tools/release-manifest/release_manifest.py [--dist DIR] [--check]
    uv run python tools/release-manifest/release_manifest.py --release v5.95.0.0
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다

#: 플러그인 내부 이름. 압축 안의 매니페스트 파일 이름이기도 하다.
INTERNAL_NAME = "FF14Accessibility"

#: 릴리스에 올라가는 산출물 이름. `AssetName`도 여기서 나온다.
ZIP_NAME = f"{INTERNAL_NAME}.zip"
INSTALLER_NAME = "FF14AccessibilityInstaller-KR.exe"

#: 이 도구가 만드는 것. `dist`의 나머지는 건드리지 않는다.
REPO_MANIFEST_NAME = "repo.json"
INSTALLER_MANIFEST_NAME = "installer.json"

#: 매니페스트 둘이 나가는 자리. `dist` 루트는 **사용자에게 그대로 줄 수 있는
#: 폴더**로 두고, 기계만 읽는 것은 여기로 내린다 - 사용 안내가 "압축을 풀면 그
#: 안에 넷이 들어 있습니다"라고 세어 주는 그 폴더라, 거기에 사람이 안 여는
#: 파일이 섞이면 무엇을 눌러야 하는지 헷갈린다.
#:
#: **릴리스에 올라갈 때는 여전히 개별 자산이다.** 받는 쪽이 URL로 직접 받으므로
#: (`installer.json`은 자기 갱신이, `repo.json`은 Dalamud가) 폴더 구조는 우리
#: 편의일 뿐이고 자산 이름에는 영향이 없다.
RELEASE_DIR_NAME = "release"

#: 안내 문서가 **폴더에 나갈 때의 이름**. 저장소의 원본은
#: `docs/korean/README.ko.md`이고, 받는 사람이 무슨 파일인지 알아야 하므로
#: 폴더 안에서는 한글이다. 같은 이름을 `tools/pack-check`도 갖고 있다.
GUIDE_NAME = "사용 안내.md"

#: 안내 문서 4장의 키만 모은 목록. 저장소의 원본은 `docs/korean/keys.md`이고
#: 같은 이름을 `tools/pack-check`도 갖고 있다.
KEYS_NAME = "단축키 목록.md"

#: `dist` 루트에 나오는 넷. 빌드가 낸 그대로이고 사람이 열어 보는 것이다.
#: 루트의 구성을 실제로 재는 것은 `tools/pack-check`의 `root_expected`이고,
#: 여기는 매니페스트를 쓰고 나서 루트가 그 넷 그대로인지 보는 자리다.
USER_FILES = (INSTALLER_NAME, ZIP_NAME, GUIDE_NAME, KEYS_NAME)

#: Dalamud 플러그인 목록에 그려지는 이름. **`InternalName`이 아니다** - 그쪽은
#: 설치된 폴더 이름이자 갱신 대조 키라 건드리면 안 된다.
#:
#: 버전만 보면 원본 모드와 구별되지 않아서 여기에 한국 서버를 드러낸다. 이름을
#: 지어내지 않았다 - 사용자가 실제로 듣는 설치 프로그램 창 제목이
#: `FF14 접근성 모드 설치 프로그램 (한국 서버)`이고(`replace/Installer/Loc.cs`),
#: 사용 안내 제목이 `FF14 접근성 모드 (한국 서버용) 사용 안내`다.
PLUGIN_DISPLAY_NAME = "FF14 접근성 모드 (한국 서버용)"


# ── 저장소 주소 셋 ─────────────────────────────────────────────────────────
#
# **하나로 두면 넷이 같이 움직인다.** 전에는 주소 하나에서 발행 대상도, 받는
# 쪽이 여는 주소도, 사람이 읽는 문서 주소도 다 파생했다. 그러면 하나만 옮겨야
# 할 때 옮길 방법이 없다 - 실제로 저장소를 옮기면서 그 셋의 시점이 갈렸다.
#
# 지금은 셋이 같은 저장소를 가리킨다. **같은 값인 것과 같은 것이어야 하는 것은
# 다르다.**

#: 발행 대상. `gh`가 릴리스를 내고 도로 받아 오는 저장소다. 주소가 아니라
#: `owner/name` 꼴인 것은 `gh`가 그 꼴을 받기 때문이다.
GH_REPO = "dnz3d4c/FF14-a11y-kr"

#: 받는 쪽이 **자산을 받는** 주소의 뿌리. 여기서 나온 주소가 `repo.json`에
#: 그대로 적히고, 설치 프로그램도 같은 문자열을 박아 둔다
#: (`replace/Installer/InstallerService.cs`의 `KrRepoUrl`). Dalamud가 `==`로
#: 대조하므로 대소문자와 후행 슬래시까지 같아야 한다 - 한 글자만 달라도
#: 모드가 목록에서 사라진다.
DOWNLOAD_REPO_URL = "https://github.com/dnz3d4c/FF14-a11y-kr"

#: **사람이 여는** 주소의 뿌리. 문서 링크와 플러그인 목록의 저장소 링크가
#: 여기서 나온다. 기계가 안 읽으므로 갈라져도 설치가 안 깨진다 - 그래서 따로
#: 둔다.
DOC_REPO_URL = "https://github.com/dnz3d4c/FF14-a11y-kr"

#: 모드 본체를 받는 주소. `repo.json`의 내려받기 링크 셋이 전부 이 값이다.
DOWNLOAD_URL = f"{DOWNLOAD_REPO_URL}/releases/latest/download/{ZIP_NAME}"

#: Dalamud에 등록되는 저장소 주소. 설치 프로그램이 이 문자열을 박아 두고
#: Dalamud가 `==`로 대조한다. 여기가 안 열리면 커스텀 저장소 경로가 통째로
#: 죽는다.
REPO_JSON_URL = f"{DOWNLOAD_REPO_URL}/releases/latest/download/{REPO_MANIFEST_NAME}"

#: 사용자가 문서를 읽는 자리. **파일로 안 주고 주소로 준다.**
#:
#: **`.md`를 받아 열면 제목 구조가 없다.** 그려 주는 프로그램이 없으면
#: `## 2. 설치`가 글자 그대로 보이고, 그러면 스크린리더 제목 탐색이 안 된다.
#: GitHub이 그려 주면 진짜 제목이라 탐색이 된다.
#:
#: **`master` 고정이다.** 판마다 값이 안 바뀌므로 나가 있는 노트를 소급해 고칠
#: 때 같은 값을 넣으면 되고, 문서를 고치면 옛 판 노트에서도 고친 것이 보인다.
DOC_BASE_URL = f"{DOC_REPO_URL}/blob/master/docs/korean"
GUIDE_DOC_URL = f"{DOC_BASE_URL}/README.ko.md"
KEYS_DOC_URL = f"{DOC_BASE_URL}/keys.md"

#: 한 릴리스에 같이 올라가야 하는 자산. 하나라도 빠지면 받는 쪽은 오류가
#: 아니라 "새 판이 없다"로 읽는다. **올리는 절차는 이 저장소에 아직 없고**,
#: 올라간 것을 도로 받아 재는 것이 `--release`다.
#:
#: **첫째만 사람이 받고 나머지 셋은 기계가 URL로 받는다.** 문서 둘은 자산이
#: 아니라 `GUIDE_DOC_URL`로 가리킨다.
RELEASE_ASSETS = (
    INSTALLER_NAME,
    ZIP_NAME,
    REPO_MANIFEST_NAME,
    INSTALLER_MANIFEST_NAME,
)

#: `repo.json`에서 내려받기 주소를 담는 자리. 셋이 같아야 한다.
DOWNLOAD_FIELDS = ("DownloadLinkInstall", "DownloadLinkUpdate", "DownloadLinkTesting")

#: 원본 `repo.json`의 필드 순서. 형식을 본뜨는 자리라 순서까지 맞춘다.
FIELD_ORDER = (
    "Author",
    "Name",
    "InternalName",
    "AssemblyVersion",
    "Description",
    "Punchline",
    "ApplicableVersion",
    "DalamudApiLevel",
    "RepoUrl",
    "Tags",
    "AcceptsFeedback",
    "DownloadLinkInstall",
    "DownloadLinkUpdate",
    "DownloadLinkTesting",
)

#: 압축 안 매니페스트가 아니라 우리가 정하는 값.
OURS = {
    "Name": PLUGIN_DISPLAY_NAME,
    "RepoUrl": DOC_REPO_URL,
    "DownloadLinkInstall": DOWNLOAD_URL,
    "DownloadLinkUpdate": DOWNLOAD_URL,
    "DownloadLinkTesting": DOWNLOAD_URL,
}

#: 한국어로 옮겨 넣는 자리. 나머지는 압축 안의 값을 그대로 쓴다.
TRANSLATED = ("Description", "Punchline")

#: 비어 있으면 만들지 않는다. Dalamud 플러그인 목록이 이 값들로 그려진다.
REQUIRED = (
    "InternalName",
    "Name",
    "AssemblyVersion",
    "DalamudApiLevel",
    "Description",
    "Punchline",
)

#: 원본 독일어 문장 -> 한국어. 문구의 근거는 `docs/korean/README.ko.md`
#: 첫머리가 모드를 소개하는 문장이다.
#:
#: **표를 키로 두는 이유**: 원본이 문구를 고치면 여기서 못 찾고 걸린다.
#: "한국어가 아니면 그냥 원문을 쓴다"로 두면 독일어가 조용히 배포된다.
GERMAN_TO_KOREAN = {
    "Macht FF14 für blinde Spieler zugänglich via NVDA/TOLK Integration, "
    "Audio-Navigation und vollständiger Tastatursteuerung.": (
        "파이널 판타지 14를 한국 서버에서 스크린 리더로 플레이할 수 있게 합니다. "
        "NVDA와 Tolk 연동, 소리 안내, 키보드만으로 하는 조작을 제공합니다."
    ),
    "FF14 für blinde Spieler via NVDA und Tastatur zugänglich machen.": (
        "파이널 판타지 14를 한국 서버에서 스크린 리더로 플레이할 수 있게 하는 모드입니다."
    ),
}

_HANGUL = re.compile(r"[가-힣]")


class ManifestError(Exception):
    """매니페스트를 만들 수 없다. 빈 값으로 내보내는 것보다 안 만드는 것이 낫다."""


def require_dist(dist: Path) -> None:
    """`dist`가 아예 없으면 여기서 멈춘다.

    **없는 것을 통과로 세지 않는다.** 이 저장소에는 `dist`를 만드는 절차가
    아직 없어서, 지금 이 도구를 부르면 반드시 여기로 온다. 그때 무엇이
    없는지를 말해야 다음 사람이 무엇을 세워야 하는지 안다.
    """
    if not dist.is_dir():
        raise ManifestError(
            f"배포 폴더가 없다: {dist}. 산출물을 만드는 절차가 이 저장소에 아직 없다 - "
            f"조립은 `tools/assemble`이 `build/`까지 낸다"
        )


# ── 압축에서 읽기 ──────────────────────────────────────────────────────────


def _parse_json(text: str, what: str) -> object:
    """JSON 하나를 읽는다. 깨졌으면 **그렇게 말한다.**

    스택트레이스로 죽으면 검사를 안 한 것과 같다 - 릴리스가 멀쩡한 것과
    검사가 못 읽은 것이 같은 얼굴이 된다. 이 도구가 존재하는 이유가 그
    부류를 가르는 것이다.
    """
    try:
        return json.loads(text)
    except ValueError as error:
        raise ManifestError(f"{what}을 못 읽었다: {error}") from error


def _parse_object(text: str, what: str) -> dict:
    """객체 하나를 담은 JSON."""
    loaded = _parse_json(text, what)
    if not isinstance(loaded, dict):
        raise ManifestError(f"{what}이 객체가 아니다: {type(loaded).__name__}")
    return loaded


def read_plugin_manifest(zip_path: Path) -> dict:
    """압축 안의 `FF14Accessibility.json`. repo.json의 값이 전부 여기서 나온다."""
    if not zip_path.is_file():
        raise ManifestError(f"압축이 없다: {zip_path}")

    name = f"{INTERNAL_NAME}.json"
    try:
        with zipfile.ZipFile(zip_path) as archive:
            if name not in archive.namelist():
                raise ManifestError(f"압축 안에 매니페스트가 없다: {zip_path} 안의 {name}")
            # 빌드가 BOM을 붙여 낼 때가 있다. `utf-8-sig`는 없어도 그대로 읽는다.
            raw = archive.read(name).decode("utf-8-sig")
    except (zipfile.BadZipFile, OSError, UnicodeDecodeError) as error:
        # 올라간 압축이 깨진 것은 이 도구가 잡아야 할 바로 그 사고다.
        raise ManifestError(f"압축을 못 읽었다: {zip_path} ({error})") from error

    return _parse_object(raw, f"{zip_path.name} 안의 {name}")


# ── repo.json ──────────────────────────────────────────────────────────────


def korean_text(field: str, value: str) -> str:
    """설명 문구를 한국어로. 한국어면 그대로, 아니면 표에서 찾는다."""
    if _HANGUL.search(value):
        return value

    korean = GERMAN_TO_KOREAN.get(value.strip())
    if korean is None:
        raise ManifestError(
            f"{field}에 한국어가 없고 옮길 문장도 표에 없다: {value!r}. "
            f"원본이 문구를 고쳤으면 GERMAN_TO_KOREAN에 새 원문을 등록해라"
        )
    return korean


def build_repo_manifest(plugin: dict) -> list[dict]:
    """Dalamud 커스텀 저장소 매니페스트. 배열 안에 객체 하나다."""
    missing = [field for field in REQUIRED if not plugin.get(field)]
    if missing:
        raise ManifestError(f"압축 안 매니페스트에 값이 없다: {', '.join(missing)}")

    entry: dict = {}
    for field in FIELD_ORDER:
        if field in OURS:
            entry[field] = OURS[field]
        elif field in TRANSLATED:
            entry[field] = korean_text(field, plugin[field])
        elif field in plugin:
            entry[field] = plugin[field]
    return [entry]


# ── installer.json ─────────────────────────────────────────────────────────


class _FixedFileInfo(ctypes.Structure):
    """`VS_FIXEDFILEINFO`. 파일 버전은 32비트 둘에 16비트씩 네 마디로 들어 있다."""

    _fields_ = [
        (name, ctypes.c_uint32)
        for name in (
            "dwSignature",
            "dwStrucVersion",
            "dwFileVersionMS",
            "dwFileVersionLS",
            "dwProductVersionMS",
            "dwProductVersionLS",
            "dwFileFlagsMask",
            "dwFileFlags",
            "dwFileOS",
            "dwFileType",
            "dwFileSubtype",
            "dwFileDateMS",
            "dwFileDateLS",
        )
    ]


def file_version(exe: Path) -> str:
    """EXE의 PE 버전 자원에서 FileVersion을 읽는다.

    **왜 파일 이름이나 csproj가 아닌가**: 읽는 쪽이 대조하는 것은 실행 중인
    EXE의 어셈블리 버전이다(`InstallerService.cs`의 자기 갱신 갈래). 그 값이
    나가는 자리가 PE 버전 자원이고, `Installer.csproj`가 `AssemblyVersion`과
    `FileVersion`을 같은 값으로 박는다. 그러니 **배포할 그 파일에서 직접 읽는
    것**이 소스와 산출물이 갈린 상태까지 잡는다.
    """
    if not exe.is_file():
        raise ManifestError(f"설치 프로그램이 없다: {exe}")

    version_dll = ctypes.WinDLL("version.dll")
    path = str(exe.resolve())

    size = version_dll.GetFileVersionInfoSizeW(path, None)
    if not size:
        raise ManifestError(f"설치 프로그램에 버전 자원이 없다: {exe}")

    buffer = ctypes.create_string_buffer(size)
    if not version_dll.GetFileVersionInfoW(path, 0, size, buffer):
        raise ManifestError(f"설치 프로그램의 버전 자원을 못 읽었다: {exe}")

    block = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not version_dll.VerQueryValueW(buffer, "\\", ctypes.byref(block), ctypes.byref(length)):
        raise ManifestError(f"설치 프로그램의 버전 자원이 비어 있다: {exe}")

    info = ctypes.cast(block, ctypes.POINTER(_FixedFileInfo)).contents
    return ".".join(
        str(part)
        for part in (
            info.dwFileVersionMS >> 16,
            info.dwFileVersionMS & 0xFFFF,
            info.dwFileVersionLS >> 16,
            info.dwFileVersionLS & 0xFFFF,
        )
    )


def normalize_version(text: str) -> str:
    """읽는 쪽이 비교하는 모양으로 맞춘다 - 숫자 네 마디다.

    `ParseVersionLoose`가 모자란 마디를 `.0`으로 채우고 나서 비교한다. 우리가
    세 마디로 내보내도 읽는 쪽에서 같아지긴 하지만, **채우기 전의 문자열이
    남아 다른 자리(`IsNewer`의 문자열 폴백)로 새면** 같은 판을 새 판으로 보고
    갱신을 무한히 다시 권한다. 마디가 다섯이거나 숫자가 아니면 그 폴백에
    떨어지므로 아예 거른다.
    """
    parts = text.strip().lstrip("vV").split(".")
    if not 1 <= len(parts) <= 4 or not all(part.isdigit() for part in parts):
        raise ManifestError(f"읽는 쪽이 못 읽는 버전이다(숫자 네 마디까지): {text!r}")
    return ".".join(parts + ["0"] * (4 - len(parts)))


def sha256(path: Path) -> str:
    """읽는 쪽(`ComputeSha256`)이 `Convert.ToHexString`을 쓴다. 대문자로 맞춘다."""
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def build_installer_manifest(exe: Path, version: str) -> dict[str, str]:
    """설치 프로그램 자기 갱신용. `TrySelfUpdateAsync`가 읽는 셋뿐이다."""
    return {
        "InstallerVersion": normalize_version(version),
        "AssetName": exe.name,
        "Sha256": sha256(exe),
    }


# ── 만들기와 다시 재기 ─────────────────────────────────────────────────────


class Manifests(NamedTuple):
    """만든 두 매니페스트. `repo.json`은 배열이고 `installer.json`은 객체다."""

    repo: list[dict]
    installer: dict[str, str]


def _files(made: Manifests) -> tuple[tuple[str, list[dict] | dict[str, str]], ...]:
    """(파일 이름, 그 파일에 들어갈 것). 쓸 때와 다시 잴 때가 같은 목록을 본다."""
    return ((REPO_MANIFEST_NAME, made.repo), (INSTALLER_MANIFEST_NAME, made.installer))


def _build(dist: Path, installer_version: str | None) -> Manifests:
    """두 매니페스트의 내용. 값은 전부 `dist`의 산출물에서 나온다."""
    exe = dist / INSTALLER_NAME
    version = installer_version if installer_version else file_version(exe)
    return Manifests(
        repo=build_repo_manifest(read_plugin_manifest(dist / ZIP_NAME)),
        installer=build_installer_manifest(exe, version),
    )


def release_dir(dist: Path) -> Path:
    """매니페스트 둘이 있는 자리. **경로는 여기 하나에서만 나온다.**"""
    return dist / RELEASE_DIR_NAME


def write_manifests(dist: Path, installer_version: str | None = None) -> Manifests:
    """매니페스트 둘을 `dist/release`에 쓴다."""
    made = _build(dist, installer_version)
    target = release_dir(dist)
    target.mkdir(parents=True, exist_ok=True)
    for name, content in _files(made):
        (target / name).write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return made


def manifest_problems(dist: Path, installer_version: str | None = None) -> list[str]:
    """이미 있는 매니페스트가 지금 산출물과 맞나. 만들지 않고 재기만 한다."""
    problems: list[str] = []
    for name, content in _files(_build(dist, installer_version)):
        path = release_dir(dist) / name
        if not path.is_file():
            problems.append(f"매니페스트가 없다: {path}")
            continue

        expected = content[0] if isinstance(content, list) else content
        loaded = _parse_json(path.read_text(encoding="utf-8"), path.name)
        if isinstance(loaded, list):
            loaded = loaded[0] if loaded else {}
        # 객체가 아니면 빈 것으로 본다. 필드마다 어긋난다고 말하게 된다.
        actual = loaded if isinstance(loaded, dict) else {}
        for field, want in expected.items():
            if actual.get(field) != want:
                problems.append(
                    f"{name}의 {field}가 산출물과 다르다: {actual.get(field)!r} != {want!r}"
                )
    return problems


# ── 릴리스를 다시 재기 ─────────────────────────────────────────────────────
#
# **`dist`를 안 본다.** `dist`가 완벽해도 업로드에서 하나 빠지면 그대로
# 나가고, 그 실패는 오류가 아니라 침묵이다 - 받는 쪽은 "새 판이 없다"로
# 읽는다. 그래서 릴리스에서 도로 받아 다시 계산한다. `tools/pack-check`가
# "설치 프로그램이 성공이라 말했다"를 안 믿고 산출물을 다시 재는 것과
# 같은 수법이다.


class ReleaseFacts(NamedTuple):
    """릴리스에서 **실제로 확인한** 것. I/O는 여기까지고 판정은 순수 함수다."""

    tag: str
    asset_names: tuple[str, ...]
    repo_manifest: list[dict]
    installer_manifest: dict
    #: 릴리스 zip 안의 `FF14Accessibility.json`. `repo.json`과 대조한다.
    plugin_manifest: dict
    exe: Path
    exe_version: str
    #: 주소 -> 200 또는 못 연 이유.
    link_status: dict[str, int | str]
    #: 초안이면 받는 쪽에서 아예 안 보인다. 내는 사람 화면에서는 정상이다.
    is_draft: bool
    #: 비공개면 자산은 멀쩡한데 주소만 404다. `gh`로는 절대 안 드러난다.
    is_private: bool


def gh_failure(tag: str, stderr: str, returncode: int, missing: str | None = None) -> ManifestError:
    """`gh`가 실패했을 때 무엇을 말할지. 못 찾은 것은 따로 말한다.

    `missing`은 "못 찾았다"에 쓸 문장이다. 릴리스를 찾을 때와 저장소를 찾을
    때가 같은 말을 하면 원인을 엉뚱한 데서 찾게 된다.
    """
    if "not found" in stderr.lower() or "404" in stderr:
        return ManifestError(
            missing or f"릴리스가 없다: {tag} ({GH_REPO}). 릴리스를 먼저 내고 다시 잰다"
        )
    return ManifestError(f"gh가 실패했다(코드 {returncode}): {stderr.strip() or '(출력 없음)'}")


def _gh(args: list[str], tag: str, timeout: int = 600, missing: str | None = None) -> str:
    """`gh`를 부르고 표준 출력을 돌려준다."""
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise ManifestError("gh를 못 찾았다. `scoop install gh` 뒤에 `gh auth login`") from error

    if result.returncode != 0:
        raise gh_failure(tag, result.stderr, result.returncode, missing)
    return result.stdout


def dotnet_runtime_url() -> str:
    """설치 프로그램이 .NET을 받아 오는 주소.

    여기서 다시 적지 않고 `tools/kr-setup/kr_profile.py`에서 가져온다. 그쪽이
    설치 프로그램(`kr/Installer/KrProfile.cs`)과 미러링돼 있고 갈라지면
    테스트가 실패한다. 사본을 하나 더 만들면 그 그물 밖에 놓인다.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kr-setup"))
    import kr_profile  # noqa: PLC0415 - 도구 사이 경로 주입이라 위에서 못 한다

    return kr_profile.DOTNET_DOWNLOAD_URL


def link_status(url: str, timeout: int = 30) -> int | str:
    """주소가 실제로 열리나. 본문은 안 읽는다.

    `gh`로는 못 보는 것을 본다 - **저장소가 비공개면 자산은 멀쩡히 있는데
    이 주소만 404다.** 받는 쪽이 쓰는 것은 이 주소뿐이다.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - 상수 주소다
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return f"못 열었다: {error}"


def repo_is_private(repo: str) -> bool:
    """저장소가 비공개인가.

    **주소가 404일 때 원인을 말하려면 이게 필요하다.** `gh`는 인증을 갖고
    있어서 비공개 저장소의 자산도 멀쩡히 보고, 그래서 자산 목록만으로는
    "올라갔는데 아무도 못 받는" 상태가 절대 안 드러난다.
    """
    listing = _parse_object(
        _gh(
            ["repo", "view", repo, "--json", "isPrivate"],
            repo,
            missing=f"저장소를 못 찾았다: {repo}",
        ),
        "gh의 저장소 정보",
    )
    return bool(listing.get("isPrivate"))


def gather_release(tag: str, workdir: Path, repo: str = GH_REPO) -> ReleaseFacts:
    """릴리스에서 받아 온다. EXE가 160MB쯤이라 여기가 오래 걸린다."""
    listing = _parse_object(
        _gh(["release", "view", tag, "--repo", repo, "--json", "assets,isDraft"], tag),
        "gh의 릴리스 정보",
    )
    asset_names = tuple(asset["name"] for asset in listing.get("assets", []))

    downloaded = {}
    for name in (REPO_MANIFEST_NAME, INSTALLER_MANIFEST_NAME, INSTALLER_NAME, ZIP_NAME):
        if name not in asset_names:
            continue  # 없는 것은 `release_problems`가 자산 목록에서 말한다
        _gh(
            [
                "release",
                "download",
                tag,
                "--repo",
                repo,
                "--pattern",
                name,
                "--dir",
                str(workdir),
                "--clobber",
            ],
            tag,
        )
        downloaded[name] = workdir / name

    exe = downloaded.get(INSTALLER_NAME)
    zip_path = downloaded.get(ZIP_NAME)
    repo_manifest = _read_repo_manifest(downloaded.get(REPO_MANIFEST_NAME))
    urls = {REPO_JSON_URL, dotnet_runtime_url()} | {
        url for field in DOWNLOAD_FIELDS if isinstance(url := repo_manifest[0].get(field), str)
    }
    return ReleaseFacts(
        tag=tag,
        asset_names=asset_names,
        repo_manifest=repo_manifest,
        installer_manifest=_read_installer_manifest(downloaded.get(INSTALLER_MANIFEST_NAME)),
        plugin_manifest=read_plugin_manifest(zip_path) if zip_path else {},
        exe=exe if exe else workdir / INSTALLER_NAME,
        exe_version=file_version(exe) if exe else "",
        link_status={url: link_status(url) for url in sorted(urls)},
        is_draft=bool(listing.get("isDraft")),
        is_private=repo_is_private(repo),
    )


def _load(path: Path, where: str = "릴리스의") -> object:
    """JSON 하나를 읽는다. 깨졌으면 그렇게 말한다 - 그것도 배포 사고다.

    `where`는 **어디서 온 파일인지**다. 릴리스에서 받은 것과 `dist`에 만든
    것이 파일 이름이 같아서, 그 말이 없으면 어느 쪽이 깨졌는지 모른다.
    """
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise ManifestError(f"{where} {path.name}을 못 읽었다: {error}") from error
    return _parse_json(raw, f"{where} {path.name}")


def _read_repo_manifest(path: Path | None) -> list[dict]:
    """못 받았으면 빈 껍데기. 없다는 말은 자산 목록이 한 번만 한다."""
    if path is None:
        return [{}]
    loaded = _load(path)
    if not isinstance(loaded, list) or not loaded or not isinstance(loaded[0], dict):
        raise ManifestError(f"릴리스의 {REPO_MANIFEST_NAME}이 객체 하나를 담은 배열이 아니다")
    return loaded


def _read_installer_manifest(path: Path | None) -> dict:
    if path is None:
        return {}
    loaded = _load(path)
    if not isinstance(loaded, dict):
        raise ManifestError(f"릴리스의 {INSTALLER_MANIFEST_NAME}이 객체가 아니다")
    return loaded


def _asset_problems(facts: ReleaseFacts) -> list[str]:
    """자산 넷이 이름까지 정확히 있나."""
    problems = []
    for name in RELEASE_ASSETS:
        if name in facts.asset_names:
            continue
        near = [other for other in facts.asset_names if other.lower() == name.lower()]
        if near:
            # 설치 프로그램은 `OrdinalIgnoreCase`로 찾아 넘어가는데, 내려받기
            # 주소는 이름을 그대로 쓴다. 한쪽만 되는 상태다.
            problems.append(f"자산 이름의 대소문자가 다르다: {near[0]} (올려야 하는 이름은 {name})")
        else:
            problems.append(f"릴리스에 자산이 없다: {name}")
    return problems


def _installer_problems(facts: ReleaseFacts) -> list[str]:
    """설치 프로그램 자기 갱신이 실제로 도나."""
    problems = []
    manifest = facts.installer_manifest

    version = manifest.get("InstallerVersion")
    parts = version.split(".") if isinstance(version, str) else []
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        problems.append(f"installer.json의 InstallerVersion이 네 마디 숫자가 아니다: {version!r}")
    elif facts.exe_version and version != facts.exe_version:
        problems.append(
            f"installer.json의 InstallerVersion이 릴리스 EXE의 PE 버전과 다르다: "
            f"{version} != {facts.exe_version}"
        )

    asset_name = manifest.get("AssetName")
    if asset_name not in facts.asset_names:
        problems.append(
            f"installer.json의 AssetName이 릴리스에 없는 자산을 가리킨다: {asset_name!r}"
        )

    if facts.exe.is_file():
        actual = sha256(facts.exe)
        if str(manifest.get("Sha256", "")).upper() != actual:
            problems.append(
                f"installer.json의 Sha256이 릴리스 EXE를 다시 계산한 값과 다르다: "
                f"{manifest.get('Sha256')!r} != {actual}"
            )
    return problems


def _why_blocked(facts: ReleaseFacts, url: str, status: int | str | None) -> str | None:
    """주소가 안 열리는 **까닭**. "404"만 말하면 받는 사람이 원인을 모른다.

    지어내지 않는다 - 아는 까닭이 없으면 모른다고 말한다. 이미 다른 줄이
    말한 까닭이면 `None`이다. 한 고장을 세 줄로 말하면 그중 아무것도 안 읽힌다.
    """
    wanted = url.rsplit("/", 1)[-1]
    if wanted not in facts.asset_names:
        return None  # 자산이 없다는 말은 위에서 이미 했다
    if facts.is_private:
        return (
            f"{url}이 {status}다. **저장소가 비공개라 받는 쪽에서 안 열린다** - "
            f"자산은 올라가 있고 `gh`로는 정상으로 보인다. 공개로 전환해야 한다"
        )
    if facts.is_draft:
        return f"{url}이 {status}다. 릴리스가 초안이라 받는 쪽에 아직 안 나간다"
    return f"{url}이 {status}다. 자산도 있고 공개인데 안 열린다 - 원인을 못 찾았다"


def _download_link_problems(facts: ReleaseFacts) -> list[str]:
    """받는 쪽이 실제로 여는 주소가 열리나."""
    problems = []
    entry = facts.repo_manifest[0] if facts.repo_manifest else {}

    links = {field: entry.get(field) for field in DOWNLOAD_FIELDS}
    install = links[DOWNLOAD_FIELDS[0]]
    for field, url in links.items():
        if url != install:
            problems.append(f"repo.json의 {field}가 다른 링크와 갈렸다: {url!r} != {install!r}")

    if isinstance(install, str):
        wanted = install.rsplit("/", 1)[-1]
        if wanted not in facts.asset_names:
            problems.append(f"repo.json의 내려받기 링크가 릴리스에 없는 파일을 가리킨다: {wanted}")

    for url in sorted({install, REPO_JSON_URL} if isinstance(install, str) else {REPO_JSON_URL}):
        status = facts.link_status.get(url)
        if status != 200 and (why := _why_blocked(facts, url, status)) is not None:
            problems.append(why)

    # 남의 주소라 `_why_blocked`의 설명(초안·비공개 저장소)이 하나도 안 맞는다.
    # 그래서 따로 잰다. 우리 자산은 아니지만 **첫 설치가 여기 매여 있다** -
    # 죽으면 갓 받은 사람이 런타임 없이 끝나고, 게임 안에서 모드가 안 뜬다.
    if (status := facts.link_status.get(dotnet_runtime_url())) != 200:
        problems.append(
            f".NET 런타임 주소가 {status}다: {dotnet_runtime_url()}. "
            f"설치 프로그램이 이 주소로 받으므로 첫 설치가 런타임 없이 끝난다"
        )
    return problems


def _repo_manifest_problems(facts: ReleaseFacts) -> list[str]:
    """올라간 `repo.json`이 받는 쪽에서 쓸 수 있는 모양인가."""
    problems = []
    entry = facts.repo_manifest[0] if facts.repo_manifest else {}
    version = entry.get("AssemblyVersion")

    # 만드는 쪽은 `GERMAN_TO_KOREAN`이 막는다. 여기는 **올라간 쪽**이다.
    # 손으로 고친 것을 올렸거나 옛 판이 올라갔으면 여기서만 걸린다.
    for field in TRANSLATED:
        if not _HANGUL.search(str(entry.get(field, ""))):
            problems.append(
                f"repo.json의 {field}에 한국어가 없다: {entry.get(field)!r}. "
                f"Dalamud 플러그인 목록에 그대로 그려진다"
            )

    # 태그가 곧 플러그인 버전이다. `ChoosePluginSourceAsync`가 태그에서 v를
    # 떼어 설치된 버전과 비교하므로, 태그가 낮으면 새 판이 올라가 있어도
    # 받는 쪽은 "이미 최신"으로 읽는다.
    if version and facts.tag.lstrip("vV") != version:
        problems.append(f"태그가 플러그인 버전과 다르다: {facts.tag} (repo.json은 {version})")

    # 올라간 zip이 repo.json이 말하는 그 판인가. 어긋나면 Dalamud가 받아
    # 놓고 같은 판을 다시 받는다.
    built = facts.plugin_manifest.get("AssemblyVersion")
    if built and version and built != version:
        problems.append(
            f"repo.json과 릴리스 압축 안 매니페스트의 버전이 다르다: {version} != {built}. "
            f"Dalamud가 받아 놓고 같은 판을 다시 받는다"
        )
    return problems


def release_problems(facts: ReleaseFacts) -> list[str]:
    """릴리스가 받는 쪽이 기대하는 모양인가. `dist`는 안 본다."""
    problems = []
    if facts.is_draft:
        # 내는 사람 화면에서는 멀쩡해 보이는데 받는 쪽에서는 아예 안 보인다.
        problems.append(f"{facts.tag}가 초안이다. 받는 쪽에서는 아예 안 보인다")

    return (
        problems
        + _asset_problems(facts)
        + _installer_problems(facts)
        + _repo_manifest_problems(facts)
        + _download_link_problems(facts)
    )


def check_release(tag: str, repo: str = GH_REPO) -> list[str]:
    """릴리스를 받아 재고 문제를 돌려준다. 받은 것은 지운다."""
    workdir = Path(tempfile.mkdtemp(prefix="ff14acc-release-"))
    try:
        return release_problems(gather_release(tag, workdir, repo))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ── 버전이 올라갔나 ────────────────────────────────────────────────────────
#
# **산출물이 바뀌었는데 버전이 그대로면 갱신이 침묵한다.** 설치 프로그램의
# `IsNewer`도 Dalamud도 버전만 보므로, 같은 번호로 다시 올리면 받는 쪽은
# "새 판이 없다"로 읽는다. 오류가 아니라서 내는 사람 화면에도 안 남는다.


def manifest_versions(directory: Path, where: str = "릴리스의") -> dict[str, str]:
    """매니페스트 둘에서 버전만 뽑는다. 없거나 비면 그 자리를 안 만든다.

    **릴리스에서 받은 폴더와 `dist/release`를 같은 함수로 읽는다.** 두 벌이
    되면 갈리고, 갈리면 비교가 거짓말을 한다.
    """
    found: dict[str, str] = {}

    repo_path = directory / REPO_MANIFEST_NAME
    if repo_path.is_file():
        loaded = _load(repo_path, where)
        entry = loaded[0] if isinstance(loaded, list) and loaded else loaded
        version = entry.get("AssemblyVersion") if isinstance(entry, dict) else None
        if isinstance(version, str) and version:
            found[REPO_MANIFEST_NAME] = version

    installer_path = directory / INSTALLER_MANIFEST_NAME
    if installer_path.is_file():
        loaded = _load(installer_path, where)
        version = loaded.get("InstallerVersion") if isinstance(loaded, dict) else None
        if isinstance(version, str) and version:
            found[INSTALLER_MANIFEST_NAME] = version

    return found


def latest_release_tag(repo: str = GH_REPO) -> str | None:
    """제일 최근 릴리스의 태그. 하나도 없으면 `None`이다.

    **`release view`가 아니라 `release list`다.** 릴리스가 없는 것을 예외가
    아니라 빈 배열로 받아야 "첫 릴리스"와 "gh가 실패했다"가 안 섞인다.
    섞이면 첫 릴리스를 영영 못 내거나, gh 고장을 첫 릴리스로 읽는다.
    """
    listing = _parse_json(
        _gh(
            ["release", "list", "--repo", repo, "--limit", "1", "--json", "tagName"],
            repo,
            missing=f"저장소를 못 찾았다: {repo}",
        ),
        "gh의 릴리스 목록",
    )
    if not isinstance(listing, list):
        raise ManifestError(f"gh의 릴리스 목록이 배열이 아니다: {type(listing).__name__}")
    if not listing:
        return None

    tag = listing[0].get("tagName") if isinstance(listing[0], dict) else None
    if not isinstance(tag, str) or not tag:
        raise ManifestError("gh의 릴리스 목록에 태그 이름이 없다")
    return tag


class BumpFacts(NamedTuple):
    """이미 나간 것과 지금 낼 것의 버전. I/O는 여기까지고 판정은 순수 함수다."""

    #: 제일 최근 릴리스의 태그. 릴리스가 하나도 없으면 `None`이다.
    latest_tag: str | None
    #: 매니페스트 이름 -> 릴리스에 나가 있는 버전.
    released: dict[str, str]
    #: 매니페스트 이름 -> 지금 `dist/release`에 있는 버전.
    local: dict[str, str]


def gather_bump_facts(dist: Path, workdir: Path, repo: str = GH_REPO) -> BumpFacts:
    """비교할 두 벌을 모은다. 매니페스트 둘만 받으므로 몇 초면 끝난다."""
    tag = latest_release_tag(repo)
    if tag is not None:
        for name in (REPO_MANIFEST_NAME, INSTALLER_MANIFEST_NAME):
            _gh(
                [
                    "release",
                    "download",
                    tag,
                    "--repo",
                    repo,
                    "--pattern",
                    name,
                    "--dir",
                    str(workdir),
                    "--clobber",
                ],
                tag,
                missing=f"릴리스 {tag}에 {name}이 없다. 나가 있는 버전을 알 수 없다",
            )

    return BumpFacts(
        latest_tag=tag,
        released=manifest_versions(workdir),
        local=manifest_versions(release_dir(dist), where="dist의"),
    )


def _version_key(text: str) -> tuple[int, ...]:
    """크기를 잴 수 있는 꼴. `normalize_version`이 거르는 것은 여기서도 못 잰다."""
    return tuple(int(part) for part in normalize_version(text).split("."))


def bump_problems(facts: BumpFacts) -> list[str]:
    """지금 낼 것이 이미 나간 것보다 새 판인가. 받아 오지 않고 재기만 한다."""
    if facts.latest_tag is None:
        return []  # 첫 릴리스다. 비교할 상대가 없는 것과 안 올린 것은 다르다

    problems = []
    risen = 0
    for name in (REPO_MANIFEST_NAME, INSTALLER_MANIFEST_NAME):
        now, before = facts.local.get(name), facts.released.get(name)
        if not now:
            problems.append(f"dist의 {name}에서 버전을 못 읽었다. 매니페스트를 먼저 만든다")
            continue
        if not before:
            problems.append(f"릴리스 {facts.latest_tag}의 {name}에서 버전을 못 읽었다")
            continue

        try:
            # 못 읽는 버전끼리 크기를 재면 통과든 실패든 근거가 없다.
            higher, lower = _version_key(now), _version_key(before)
        except ManifestError as error:
            problems.append(f"{name}의 버전을 비교할 수 없다: {now} vs {before} ({error})")
            continue

        if higher < lower:
            problems.append(
                f"{name}의 버전이 릴리스보다 낮다: {now} < {before}. "
                f"내리면 이미 깐 쪽에서 갱신이 영영 안 뜬다"
            )
        elif higher > lower:
            risen += 1

    if not problems and not risen:
        problems.append(
            f"릴리스 {facts.latest_tag}와 버전이 똑같다. 산출물이 바뀌었으면 갱신이 "
            f"침묵한다 - csproj의 네 번째 마디를 올려라. 같은 판을 그대로 다시 "
            f"올리는 것이면 이 검사를 부르지 않는다"
        )
    return problems


def check_bump(dist: Path, repo: str = GH_REPO) -> tuple[BumpFacts, list[str]]:
    """버전을 재고 잰 것과 문제를 함께 돌려준다. 받은 것은 지운다."""
    workdir = Path(tempfile.mkdtemp(prefix="ff14acc-bump-"))
    try:
        facts = gather_bump_facts(dist, workdir, repo)
        return facts, bump_problems(facts)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main(argv: list[str]) -> int:
    console.setup()
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="릴리스 매니페스트를 산출물에서 만든다")
    parser.add_argument("--dist", default=str(repo / "dist"))
    parser.add_argument("--check", action="store_true", help="만들지 않고 산출물과 대조만 한다")
    parser.add_argument(
        "--print-version",
        action="store_true",
        help="플러그인 버전만 한 줄로 낸다. 릴리스 태그를 이 값으로 짓는다",
    )
    parser.add_argument(
        "--release",
        metavar="태그",
        help="릴리스에 실제로 올라간 것을 받아 다시 잰다. 자산을 내려받아 몇 분 걸린다",
    )
    parser.add_argument(
        "--check-bump",
        action="store_true",
        help="이미 나간 릴리스보다 버전이 올랐나. 자산을 올리기 전에 부른다",
    )
    args = parser.parse_args(argv[1:])

    dist = Path(args.dist)
    try:
        # 릴리스를 낸 다음에 돌린다. `--check`는 `dist`가 자기 자신과 맞나를
        # 보고, 이쪽은 **올라간 것**을 받아 잰다 - 업로드에서 하나 빠진 것은
        # `dist`를 아무리 봐도 안 나온다.
        if args.release:
            problems = check_release(args.release)
            if problems:
                print(f"== 릴리스 {args.release}: 확인 필요 ==\n")
                for problem in problems:
                    print(f"  - {problem}")
                return 1
            print(f"== 릴리스 {args.release}: 받는 쪽이 읽을 수 있다 ==")
            print(f"  자산 {len(RELEASE_ASSETS)}개, 해시·버전·주소 대조 통과")
            return 0

        # 아래 넷은 전부 `dist`를 읽는다. 없으면 여기서 멈춘다.
        require_dist(dist)

        # **자산을 올리기 전에** 돌린다. 산출물이 바뀌었는데 버전이 그대로면
        # 받는 쪽은 갱신을 아예 안 본다 - 오류가 아니라 침묵이라, 올리고 나면
        # 아무 데서도 안 드러난다.
        if args.check_bump:
            facts, problems = check_bump(dist)
            if problems:
                print("== 릴리스 버전: 안 올랐다 ==\n")
                for problem in problems:
                    print(f"  - {problem}")
                return 1
            if facts.latest_tag is None:
                print("== 릴리스 버전: 첫 릴리스다 ==")
                print("  비교할 릴리스가 없다")
                return 0
            print(f"== 릴리스 버전: {facts.latest_tag}보다 새 판이다 ==")
            for name in sorted(facts.local):
                print(f"  {name} {facts.released.get(name)} -> {facts.local[name]}")
            return 0

        # 태그가 곧 플러그인 버전이다 - 설치 프로그램이 태그에서 v를 떼어
        # 설치된 버전과 비교한다(`ChoosePluginSourceAsync`). 그래서 손으로
        # 짓지 않고 배포할 압축에서 그대로 뽑는다.
        if args.print_version:
            print(build_repo_manifest(read_plugin_manifest(dist / ZIP_NAME))[0]["AssemblyVersion"])
            return 0

        if args.check:
            problems = manifest_problems(dist)
            if problems:
                print("== 릴리스 매니페스트: 확인 필요 ==\n")
                for problem in problems:
                    print(f"  - {problem}")
                return 1
            print("== 릴리스 매니페스트: 산출물과 맞는다 ==")
            return 0

        made = write_manifests(dist)
    except ManifestError as error:
        print(f"== 릴리스 매니페스트: 만들지 못했다 ==\n\n  - {error}", file=sys.stderr)
        return 1

    plugin, installer = made.repo[0], made.installer
    print("== 릴리스 매니페스트 ==")
    print(f"  {release_dir(dist) / REPO_MANIFEST_NAME}")
    print(
        f"    {plugin['InternalName']} {plugin['AssemblyVersion']} "
        f"(Dalamud API {plugin['DalamudApiLevel']})"
    )
    print(f"  {release_dir(dist) / INSTALLER_MANIFEST_NAME}")
    print(f"    {installer['AssetName']} {installer['InstallerVersion']}")
    print(f"    SHA-256 {installer['Sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
