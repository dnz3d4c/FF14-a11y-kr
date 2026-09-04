# ko-terms — 게임이 쓰는 한국어 낱말을 뽑는다

모드가 말하는 낱말과 게임 화면에 뜨는 낱말이 다르면 사용자가 이름을 두 개 외워야 한다. 그래서 게임이 쓰는 말을 그대로 써야 하는데, **지어내면 안 된다.**

옛 저장소가 그걸 한 번 겪었다. `Aetheryte`를 "에테라이트"라고 스킬에 **결정으로** 박아 놨는데 그때는 확인한 적이 없었다. 지금은 확인됐다(Addon 2723행 `에테라이트 전송망`) — 답이 맞았다는 게 아니라, **맞는지 모르고 적었다는 게 문제였다.**

## 쓰는 법

이 저장소에는 `run\` 디렉토리가 없다. `dotnet`을 직접 부른다. 그런데 `PATH`의 `dotnet`은 이 컴퓨터에서 런타임만 있고 SDK가 없어서, SDK가 든 쪽을 지목해야 한다. 아래 명령이 실제로 돌려 본 것이다.

어떤 언어가 들어 있는지 본다.

"C:\Users\advck\scoop\apps\dotnet-sdk\current\dotnet.exe" run --project tools\ko-terms\koterms.csproj -c Release -v quiet -- langs --sheet all

전 시트를 TSV로 뽑는다.

"C:\Users\advck\scoop\apps\dotnet-sdk\current\dotnet.exe" run --project tools\ko-terms\koterms.csproj -c Release -v quiet -- dump tools\ko-terms\out --sheet all

행 번호를 알면 바로 꺼낸다.

"C:\Users\advck\scoop\apps\dotnet-sdk\current\dotnet.exe" run --project tools\ko-terms\koterms.csproj -c Release -v quiet -- row 2723

아는 언어로 찾는다 (제약은 아래).

"C:\Users\advck\scoop\apps\dotnet-sdk\current\dotnet.exe" run --project tools\ko-terms\koterms.csproj -c Release -v quiet -- find Target

`--sheet`를 빼면 `Addon`이다. 그래서 `row 2723`은 Addon 2723행을 낸다.

뽑은 낱말은 `korean/terms.json`에 **시트와 행 번호와 원문을 붙여** 남긴다. 번호 없는 줄은 "어디서 봤는지 모르는 용어"고, 그건 지어낸 것과 구분이 안 된다.

## 시트가 넷이다

`Addon`만 보면 안 된다. **Addon에서 0건인 것은 "게임에 없다"가 아니라 "그 시트 밖"이다.** 소환수 이름은 Addon에 한 건도 없고 `Pet`과 `Action`에 있다.

| 시트 | 무엇이 있나 | 텍스트 열 | KR 행 수 |
|------|-------------|-----------|----------|
| Addon | UI 문자열, 설정 항목, 안내 문장 | `Text` | 19,592 |
| Action | 기술 이름 | `Name` | 51,501 |
| Pet | 소환수 이름 | `Name` | 104 |
| Status | 상태 이름 | `Name` | 5,601 |

열 이름이 시트마다 다르다. `Addon`만 `Text`고 나머지 셋은 `Name`이다 — 짐작한 것이 아니라 `Lumina.Excel.Sheets`의 형 정의를 반사로 읽어 확인했다.

행 수가 적은 시트는 통째로 훑는 것이 빠르다. `Pet`은 104행이라 덤프를 그대로 읽으면 된다.

## 어떻게 읽나

KR 클라이언트의 `game\sqpack`을 Lumina로 직접 읽는다. **게임을 켤 필요가 없다.** 로그를 뒤지는 방법은 그 화면에 들어가 본 적이 있어야 하는데, 이건 그 제약이 없다.

`PanicOnSheetChecksumMismatch`를 끈다. 추측이 아니라 KR 시트가 Lumina의 글로벌 기준 스키마와 체크섬이 어긋나기 때문이고, KR Dalamud 언어 패치도 같은 이유로 이걸 끈다.

`Lumina.dll`과 `Lumina.Excel.dll`은 `$(DALAMUD_HOME)`에서 참조한다. 재배포하지 않는다 — 업스트림 `tools/charamake-dump`와 같은 방식이다. 그 환경변수가 비어 있으면 빌드가 안 된다.

## 제약 하나 — 이 클라이언트에는 한국어밖에 없다

`find`는 **아는 언어로 찾아 그 행의 한국어를 읽는** 방식이다. 한국어로 찾으면 짐작한 낱말이 그대로 답이 되어 버려서, 확인이 아니라 자기 확인이 된다.

그런데 KR sqpack에는 한국어 한 종뿐이다(`langs`로 확인). 그래서 `find`는 지금 못 쓰고, **행 번호를 아는 경우에만** `row`로 볼 수 있다. 시트를 넷으로 넓혀도 이 제약은 그대로다.

행 번호는 이렇게 얻는다.

1. **업스트림 소스가 적어 둔 번호.** 예를 들어 `AccessibilityStrings.Chat.cs`가 채팅 설정 블록을 "Addon 1205-1290행"이라고 적어 뒀다
2. **구조로 짚기.** 그 범위를 통째로 훑으면 무엇이 무엇인지 배치로 드러난다

두 번째가 실제로 통한 예가 소환사 용어다. `Action` 25802~25807이 `루비 소환`·`토파즈 소환`·`에메랄드 소환` 다음에 `이프리트 소환`·`타이탄 소환`·`가루다 소환`으로 이어져, 보석 셋과 소환수 셋이 같은 차례로 붙어 있다. `Pet` 30~32행(`이프리트 루비`·`타이탄 토파즈`·`가루다 에메랄드`)이 같은 짝을 따로 확인해 준다.

## 게임 텍스트를 저장소에 넣지 않는다

`tools/ko-terms/out/`은 `.gitignore`에 있다. 스퀘어에닉스의 텍스트를 통째로 재배포하지 않는다. **우리가 실제로 쓰는 낱말만** 출처와 함께 `korean/terms.json`에 남긴다.

## 무엇이 검사되나

`tools/ko-terms/tests`가 저장소 루트의 pytest에서 돈다.

- 줄마다 시트와 행 번호가 있는가 — 늘
- 한국어가 그 행의 원문 안에 있는가 — 늘
- **게임이 지금도 같은 말을 하는가** — 대장이 가리키는 시트의 덤프가 다 있을 때만. 게임이 올라가며 낱말을 바꾸면 여기가 빨개진다
- **못 찾았다고 적은 낱말이 정말 없는가** — Addon 덤프가 있을 때만

마지막 것이 중요하다. `채팅`은 Addon 19,592행에 **0건**이다. 게임은 그 낱말을 안 쓰고 `로그`·`대화`를 쓴다. 짐작했으면 틀렸을 자리다.

그 검사가 **Addon만 본다**는 것도 같이 봐야 한다. `not_found`에 적힌 설명이 전부 Addon 기준으로 쓰여 있어서다. 시트를 넓히면 검사가 설명보다 넓은 것을 주장하게 된다 — 실제로 `장판`은 Addon에 0건이지만 `Action`에는 `장판 뒤집기`가 7행 있다(뜻이 다른 보스 기술 이름이다). 넓히려면 줄마다 어느 시트를 뒤졌는지부터 적어야 한다.
