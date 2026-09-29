# 설치 프로그램이 힐 모니터 음성 파일을 안 깐다

**상태**: 초안
**대상**: v6.08.35의 `Installer/InstallerService.cs` `DeployPluginFiles`(951행), `FF14Accessibility/Services/UpdateService.cs` `ExtractFiles`(342행)
**심각도**: 높음. 설치 프로그램으로 깐 사용자 전원에게 힐 모니터가 소리를 안 낸다

## 증상

힐 모니터를 켜면 "불러오는 중"까지만 들리고 그 뒤로 아무 소리가 없다. 재시도도 없다.

## 원인

배포 압축에는 음성 122개가 `assets/partymonitor/*.mp3`로 들어 있다. 플러그인은 그것을 DLL 옆의 `assets\partymonitor`에서 찾는다(`Plugin.cs`의 `PartyMonitorService` 생성).

설치 프로그램의 `DeployPluginFiles`는 압축 루트의 파일만 복사한다. 루트가 비었을 때만 하위 폴더를 읽고, 그때도 `Path.GetFileName`으로 폴더 구조를 버린다. 그래서 설치본에 `assets` 폴더가 생기지 않는다.

그러면 `NumberVoiceBank.Load`가 `DirectoryNotFoundException`을 던지고 `_failed`가 선다. `PartyMonitorService`는 `HasFailed`를 보고 재시도 없이 조용히 남는다.

한국어판 설치본에서 직접 확인했다. 배포 압축에는 mp3가 122개 있고, 설치 폴더에는 `assets`가 없었다(2026-09-29).

## 자기 갱신도 같은 모양이다

`UpdateService.ExtractFiles`는 루트 항목만 받는다. 주석이 밝히는 까닭은 둘이다. 하나는 `System.Speech.dll`이 루트와 `runtimes/` 아래에 두 벌 있다는 것이고, 다른 하나는 경로 순회를 막는 것이다. 둘 다 맞는 판단이지만 `assets/`까지 같이 버린다.

자기 갱신은 현재 플러그인 폴더에 덮어쓰므로(258행), 이미 깔린 음성은 남는다. 대신 설치 프로그램으로 깔아 음성이 처음부터 없는 사용자는 자기 갱신으로도 받지 못한다. 원본이 음성 파일을 더하거나 바꾸는 날에도 그 변경이 안 온다.

## 왜 원본 쪽에서 안 보였나

미확인 추정이다. 원본 csproj의 Debug 빌드가 음성 파일을 개발용 폴더로 따로 복사한다(`FF14Accessibility.csproj:145`). 개발 환경에서는 설치 프로그램을 거치지 않고도 음성이 있어서 결함이 가려졌을 수 있다.

## 고칠 방향

설치 프로그램과 자기 갱신이 루트 파일에 더해 `assets/` 트리를 상대 경로 그대로 받는다. `runtimes/`는 지금처럼 버린다. 대상 경로가 플러그인 폴더 밖으로 나가면 거부한다.

## 보내는 기준

[rejected.md](rejected.md)의 다섯을 다 넘긴다.

1. 코드에 한국이 안 나온다
2. 모든 언어의 사용자에게 이롭다. 설치 프로그램으로 깐 사람은 누구나 힐 모니터가 무음이다
3. 원본의 결정을 뒤집지 않는다. `runtimes/`를 버리는 판단은 그대로 둔다
4. 소스만으로 판정된다. 복사 코드와 음성을 여는 경로가 맞지 않는다
5. 명백한 오류다. 기능이 필요로 하는 파일을 배포물에 넣고 설치에서 버린다

## 우리 쪽 사정

설치 프로그램은 우리가 `replace/Installer/InstallerService.cs`로 통째로 대체해 배포한다. 안 고치면 한국어판 사용자 전원에게 기능이 죽은 채 나가므로, 원본 결함이지만 그 파일에서 고쳤다(`DeployAssetTree`). 원본이 고치면 우리 수정을 원본 쪽 모양에 맞춘다.

자기 갱신은 원본 파일이라 고치지 않았다. 배포 검사 `tools/pack-check`가 설치본에 음성 122개가 다 있는지 이름으로 잰다.
