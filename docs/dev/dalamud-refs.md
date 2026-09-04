# 빌드에 필요한 Dalamud 참조

원본 csproj가 `DALAMUD_HOME` 아래에서 어셈블리 여섯을 찾는다. 그것을 로컬과 CI에서 어떻게 마련하는지 적는다.

## 여섯 중 둘만 한국 클라이언트 전용이다

| 파일 | 출처 | 라이선스 |
|------|------|----------|
| `Dalamud.dll` | 한국 클라이언트 빌드. [MiqoKR/kr-dalamud-updater](https://github.com/MiqoKR/kr-dalamud-updater)가 만든다 | AGPL-3.0 |
| `FFXIVClientStructs.dll` | 게임 7.51에 고정된 것. 공식 배포본은 7.55라서 다르다 | MIT |
| `Lumina.dll` | 공식 배포본과 **바이트가 같다** | |
| `Lumina.Excel.dll` | 공식 배포본과 바이트가 같다 | |
| `InteropGenerator.Runtime.dll` | 공식 배포본과 바이트가 같다 | |
| `ImGuiScene.dll` | 공식 배포본과 바이트가 같다 | |

뒤의 넷은 <https://goatcorp.github.io/dalamud-distrib/latest.zip>에서 받는다. **받은 것이 정말 같은지 sha256으로 확인한다** — 공식 판이 올라가면 어느 날 달라질 수 있고, 그때 조용히 다른 어셈블리로 빌드하면 안 된다.

**"바이트가 같다"는 것을 2026-09-04에 실제로 쟀다.** 공식 zip을 받아 한국 클라이언트 설치본의 같은 파일과 해시를 대조했고 넷 다 일치했다. 물려받은 주장을 그대로 옮긴 것이 아니다.

## 재배포하지 않는다

이 여섯은 **빌드할 때 링크만 하는 참조**다. 릴리스 산출물에는 들어가지 않고, 실행할 때는 사용자 자신의 한국 클라이언트 Dalamud 설치본이 준다.

이 프로젝트는 Dalamud와 같은 AGPL-3.0이다. Dalamud의 대응 소스는 위 저장소의 같은 태그에 있다.

## 로컬

`DALAMUD_HOME`이 이미 한국 런처의 Hooks 디렉토리를 가리키고 있다면 그대로 빌드된다. 확인은 이 한 줄로 한다.

    ls "$DALAMUD_HOME"

여섯이 다 있으면 `dotnet build -c Release`가 그대로 된다.

**Debug로 빌드하지 않는다.** 원본 csproj의 `DeployToDevFolder` 타깃이 Debug 조건이라, Debug 빌드는 결과를 개발용 플러그인 자리로 자동 복사한다. 정식 자리와 상호 배타적이라 같이 있으면 같은 모드가 두 번 적재되고, 더 나쁘게는 들리는 것과 낸 것이 갈린 채로 귀 판정을 요청하게 된다.

## CI

러너에는 한국 클라이언트가 없으므로 둘을 어딘가에서 받아야 한다. 이 저장소의 별도 릴리스에 올려 두었고 워크플로가 거기서 받는다.

<https://github.com/dnz3d4c/FF14-a11y-kr/releases/tag/dalamud-kr-15.0.3.2>

- 태그는 어셈블리 판을 그대로 쓴다.
- 자산은 두 `.dll`과 `SHA256SUMS.txt`, 그리고 출처와 라이선스를 적은 `README.txt`다.
- **`SHA256SUMS.txt`는 붙어 있는 둘이 아니라 여섯 전부를 담는다.** 그래야 워크플로가 공식 zip에서 꺼낸 넷을 대조할 수 있다. 둘만 담으면 "바이트가 같다"를 믿는 수밖에 없다.

**어셈블리 판이 오르면 릴리스를 새로 만든다.** 같은 태그에 자산을 갈아 끼우지 않는다 — 지난 판으로 되돌려 빌드해 볼 수 없게 된다.

**참조 릴리스는 반드시 `--prerelease`로 만든다.** 이것을 빠뜨리면 깃허브가 그 릴리스를 `latest`로 치고, 그 순간 **받는 사람이 여는 주소가 통째로 404가 된다.**

    https://github.com/dnz3d4c/FF14-a11y-kr/releases/latest/download/repo.json
    https://github.com/dnz3d4c/FF14-a11y-kr/releases/latest/download/FF14AccessibilityInstaller-KR.exe

달라무드가 저장소를 조회하는 자리와 사람이 설치 파일을 받는 자리가 둘 다 저 꼴이다. 참조 릴리스에는 그런 이름의 자산이 없으므로 **오류가 아니라 침묵으로** 끊긴다 — 우리 쪽에서는 아무 신호도 안 난다.

2026-09-04에 실제로 그 상태였다. `dalamud-kr-15.0.3.2`가 `latest`였고 두 주소가 404였으며, `v5.95.0.0`을 내면서 발행 시각이 더 나중이라 저절로 풀렸다. **저절로 풀린 것은 고쳐진 것이 아니다** — 다음 참조 릴리스가 올라가는 순간 도로 뺏긴다. 그래서 그 릴리스를 prerelease로 돌려 두었고, 앞으로 만드는 것도 그렇게 한다.

우리 판을 고르는 쪽은 이미 면역이다. `release_manifest.latest_release_tag`가 `v` 네 마디 태그만 이전 판으로 본다. 하지만 **깃허브의 `latest`는 우리가 정하는 값이 아니라서 그 검사로는 못 막는다.**

**버전 상수를 한 곳에만 둔다.** 기존 저장소는 워크플로 둘에 같은 값을 두 벌로 갖고 있었고, 갈리는 것을 막는 장치가 "테스트가 YAML을 grep한다"뿐이었다.
