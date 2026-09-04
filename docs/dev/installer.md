# 설치 프로그램과 런처

`Installer/`와 `Launcher/`를 원본 위에 얹는 방식과, 그렇게 가른 까닭이다. 조립 도구 자체의 명세는 `docs/dev/assemble.md`에 있다.

## 무엇을 어느 갈래로 얹었나

원본 `v5.95`와 한국어판 사이의 차이를 파일마다 재서 갈랐다. 아래가 그 실측이다.

| 파일 | hunk | 원본 줄 수 | 추가/삭제 | 갈래 |
|------|------|-----------|----------|------|
| `Installer/InstallerService.cs` | 80 | 1,020 | +1,370 / -177 | `replace/` |
| `Installer/Loc.cs` | 12 | 446 | +415 / -4 | `replace/` |
| `Installer/LanguageDialog.cs` | 14 | 93 | +40 / -18 | `replace/` |
| `Installer/MainForm.cs` | 5 | 188 | +8 / -0 | `graft` 규칙 4개 |
| `Installer/Program.cs` | 3 | 55 | +27 / -1 | `graft` 규칙 2개 |
| `Installer/FF14AccessibilityInstaller.csproj` | 3 | 46 | +20 / -2 | `graft` 규칙 3개 |
| `Installer/KrProfile.cs` | - | 없음 | +737 | `kr/` |
| `Installer/KrCheck.cs` | - | 없음 | +123 | `kr/` |
| `Launcher/FF14AccessibilityPlay.csproj` | - | 없음 | +43 | `kr/` |
| `Launcher/Play.cs` | - | 없음 | +52 | `kr/` |

`Installer/SelfUpdate.cs`는 변경이 0줄이라 **어디에도 두지 않는다.** 원본 것이 그대로 쓰인다.

## `InstallerService.cs`를 `replace/`로 둔 것은 대가를 알고 한 판단이다

`replace/`는 위험한 부류다(`docs/dev/assemble.md`의 "원본 파일을 다루는 방식 셋"). 원본의 개선을 조용히 덮어쓸 수 있어서, 다른 두 갈래로 될 일이면 그쪽을 고른다. 이 파일은 그럴 수가 없다.

- **hunk가 80개다.** 지금 `graft/rules.json`에서 규칙이 가장 많은 파일이 `AccessibilityStrings.cs`의 7개다. 규칙으로 옮기면 한 파일에 규칙 80개가 생기고, 규칙 하나하나가 저마다 앵커를 갖는다.
- **앵커가 80개면 깨질 자리도 80개다.** 원본이 근처 한 줄을 고칠 때마다 "앵커를 못 찾았다"가 뜨고, 그 80개를 사람이 손으로 다시 맞춘다. 부분 삽입이 통째 대체보다 나은 까닭은 실패가 좁고 이름이 붙는다는 것인데, 규칙이 80개면 그 이점이 남지 않는다.

대가는 둘이고, 둘 다 알고 진다.

- **원본 1,020줄 가운데 안 건드린 843줄을 우리 사본이 떠안는다.** 그 줄들에 대한 원본의 개선은 우리가 사본을 손보기 전까지 `build/`에 안 들어온다.
- **기준선 경고가 거의 매 판 울린다.** `InstallerService.cs`는 원본이 자주 고치는 파일이다.

**그 파일에서 기준선 경고는 고장이 아니라 정상 신호다.** 경고가 뜨면 원본의 그 판을 열어 우리 사본에 옮길 것이 있는지 보고, 옮겼으면 `replace/upstream-baseline.json`의 지문도 같이 옮긴다. 경고를 없애려고 지문만 갱신하면 그 확인 절차 자체가 사라진다.

## 저장소 주소를 옮기는 일

새 저장소는 `dnz3d4c/FF14-a11y-kr`이다. `InstallerService.cs`에서 옛 주소를 쓰던 자리 셋(`AccessibilityRepoName`, `KrRepoUrl`, `KrReleasePage`)이 전부 새 주소를 가리킨다. `AccessibilityRepoOwner`는 바뀌지 않는다.

옛 주소는 상수 `LegacyKrRepoUrl` 하나로만 남아 있다. **쓰는 데가 아니라 알아보는 데 쓴다.** 이미 배포된 판이 사용자의 `dalamudConfig.json`에 옛 주소를 써 넣어 두었고, 새 EXE가 새 주소를 더하기만 하면 그 기계에는 두 항목이 남는다. 둘 다 같은 모드를 내주므로 모드 목록에 같은 것이 두 번 오르고, 그중 `InstalledFromUrl`과 맞는 하나만 업데이트를 받는다. 옛 주소가 언젠가 응답을 멈추면 그 항목은 매번 실패하는 조회가 된다.

그래서 `EnsureThirdPartyRepo`가 어느 갈래로 가든 옛 항목을 안 남긴다.

1. 새 주소 항목이 이미 있으면 — 그것을 켜고, 옛 항목을 전부 목록에서 뺀다.
2. 새 주소 항목이 없고 옛 것이 있으면 — 첫 옛 항목의 `Url`을 새 주소로 **고쳐 쓰고** 켠다. 나머지 옛 항목은 뺀다. 지우고 새로 넣지 않는 까닭은 그 자리의 다른 필드를 우리가 모르기 때문이다.
3. 둘 다 없으면 — 새로 넣는다.

1번과 2번은 사용자가 이미 갖고 있던 설정을 바꾼 것이라 `RepoState.Moved`로 돌아오고, 그때 `KrRepoMoved` 안내가 로그에 남는다. 조용히 고치지 않는다.

**대조는 `StringComparison.Ordinal`로 한다.** 달라무드가 `InstalledFromUrl`을 `==`로 견주므로, 대소문자만 다른 두 표기는 그쪽에 두 저장소다. 여기서 그 둘을 하나로 치면 어느 저장소에도 안 걸리는 항목이 나온다.

`PointManifestAtRepo`도 같은 `KrRepoUrl`을 받는다. **그 둘을 달라무드가 `==`로 대조하므로 한쪽만 고치면 모드가 목록에서 사라진다.**

## 빌드 순서

**런처를 먼저 퍼블리시해야 설치 프로그램이 빌드된다.** 설치 프로그램 csproj가 런처의 단일 파일 퍼블리시 산출물을 `EmbeddedResource`로 끌어오는데, 그 자리에 **조건을 일부러 안 걸었다.**

런처가 없으면 빌드가 거기서 서야 한다. 선택으로 만들면 끝까지 도는데 바로 가기만 조용히 안 놓이는 설치 프로그램이 나오고, 그것은 화면을 못 보는 사람에게는 아무 신호가 없는 실패다.

퍼블리시된 파일을 넣는 까닭은 런처가 framework-dependent라서다. 빌드 산출물은 exe와 dll과 runtimeconfig 셋인데, 설치 프로그램이 자원에서 꺼내는 것은 한 파일이다.
