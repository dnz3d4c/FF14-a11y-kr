# 승강기 탐침이 자기 문장을 독일어로 발화한다

**상태**: 초안. 아래 `보낼 것인가`대로 **보내지 않는다**
**대상**: `FF14Accessibility/Services/LiftProbe.cs` (파일 전체가 `#if DEBUG`)
**심각도**: 낮음. 배포되는 Release 빌드에는 이 클래스가 컴파일되지 않는다

## 증상

`LiftProbe`가 사용자에게 말하는 다섯 자리가 전부 `Loc.Pick`을 안 거치고 독일어 리터럴을 `_tolk.SpeakInterrupt`에 바로 넣는다. 갈림길이 없어서 언어 설정과 무관하다.

```csharp
// :88   측정이 도는 중에 다시 부르면
_tolk.SpeakInterrupt("Aufzug-Sonde abgebrochen.");
// :96   잴 대상이 없을 때
_tolk.SpeakInterrupt("Aufzug-Sonde: kein Spieler.");
// :106-107  측정을 시작하며
_tolk.SpeakInterrupt($"Aufzug-Sonde laeuft, {TrackDuration.TotalSeconds:F0} Sekunden. "
                     + "Jetzt auf den Aufzug stellen und ihn ausloesen.");
// :119  20초가 지나 끝날 때
_tolk.SpeakInterrupt("Aufzug-Sonde fertig.");
// :160  세로 이동을 감지했을 때
_tolk.SpeakInterrupt($"Du faehrst. Hoehe {(moved.Y > 0 ? "steigt" : "faellt")}.");
```

앞 넷은 `Start`에 있어 사람이 `/acc lift`를 쳤을 때만 나온다. **`:160`만 `Update`에 있다** — 측정이 도는 20초 동안 프레임마다 재다가, 가로 이동 없이 세로로 0.3미터 넘게 움직이면 아무도 아무것도 안 쳤는데 스스로 말한다.

**여섯 리터럴에 움라우트가 하나도 없다.** 원본이 이 파일에서만 `laeuft`·`ausloesen`·`faehrst`·`Hoehe`로 풀어 썼다. 그래서 움라우트 문자셋으로 독일어를 가르는 검사에는 여섯 다 안 걸린다 — `tools/ko-speech`가 발화 싱크 갈래(`speech`)로 잡았다.

## 배포 빌드에는 안 들어간다

셋을 읽어서 확인했다.

- `LiftProbe.cs`의 1행이 `#if DEBUG`이고 197행이 `#endif`다. **파일 전체가 그 안이다**
- 유일한 호출부인 `Plugin.cs`의 `case "lift"`/`case "liftprobe"`도 `#if DEBUG` 안이다(`:752-781`). 필드 선언과 생성(`:83`, `:339`)도 같다
- 배포물은 `dotnet build -c Release`로 만든다(`tools/pack/pack.py:204`)

즉 사용자가 이 문장을 들을 경로가 없다. 들을 수 있는 사람은 Debug로 직접 빌드한 개발자뿐이다.

## 왜 그래도 적나

**우리 검사가 이 자리를 처음 잡았고, 다음에 또 잡을 것이기 때문이다.** 여섯 리터럴이 `Pick` 밖에 맨몸으로 앉아 있는 것은 사실이라, 판정 없이 두면 다음 사람이 같은 조사를 처음부터 다시 한다. `tools/ko-speech`의 골든이 이 파일을 그래서 담고 있다.

그리고 조건이 바뀌면 심각도가 바뀐다. `#if DEBUG`가 걷히거나 이 탐침이 정식 기능이 되면 그날로 독일어가 사용자에게 나간다.

## 보낼 것인가 — 안 보낸다

[rejected.md](rejected.md)의 기준 둘을 못 넘긴다.

- **기준 2(다른 클라이언트에서도 고쳐진다)**: 탐침은 어느 로케일의 사용자에게도 안 닿는다. 고쳐서 이익을 보는 사람이 없다
- **기준 5(명백한 기존 로직의 오류다)**: 원본은 독일어로 개발된다. 개발자용 탐침을 자기 언어로 두는 것은 오류가 아니라 범위 밖으로 둔 결정으로 읽히고, 코드를 읽은 사람이 "이건 버그다"에서 갈린다

`rejected.md`가 정한 대로, 못 보내는 사안도 여기 남기되 보낼 목록에는 안 올린다.

**다시 낼 조건**: `#if DEBUG` 밖으로 나오거나, 원본이 탐침 발화도 `Loc.Pick`을 거치게 하겠다고 정할 때.

## 우리 쪽 사정

`tools/ko-speech`의 골든이 이 파일의 여섯 자리를 전부 담고 있고, `why`가 위 사실을 가리킨다. 대장(`korean/strings.json`)에는 안 넣는다 — 사용자가 못 듣는 문장을 대장에 쌓으면 미적용 숫자가 뜻을 잃는다. `#if DEBUG` 밖으로 나오면 그때 옮긴다. `Services/CollisionProbe.cs`도 같은 판단이다.
