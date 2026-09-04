# 기본 키 Strg+F5가 야외에서 독일어 두 문장을 발화한다

**상태**: 초안. 아래 판정대로 **보낸다**
**대상**: `FF14Accessibility/Services/NavigationService.cs:2403`·`:2430`·`:2543`
**심각도**: 중간. 기본 키 하나로 닿고, 독일어를 모르는 사용자는 두 문장을 통째로 못 알아듣는다

## 증상

야외에서 `Strg+F5`를 누르면 독일어 두 문장이 이어서 나온다. 갈림길이 아예 없어서 언어 설정과 무관하다.

```
Objekt-Sonde: 12 Objekte im Log.
Marker-Sonde: 3 Event, 7 Minimap, 5 Orte im Log.
```

플레이어를 못 읽는 상태면 대신 이것이 나온다.

```
Objekt-Sonde: kein Spieler.
```

세 자리 다 `_tolk.SpeakInterrupt`에 독일어 리터럴을 바로 넣는다. `Loc.Pick`을 안 거친다.

## 어느 조건에서 그 갈래로 떨어지나

`Strg+F5`는 **기본 키다.** 사람이 따로 걸어야 하는 값이 아니다.

```csharp
// Configuration.cs:57
public string KeyDumpUI       = "Strg+F5";          // Node-Tree des aktuellen Addons auf Desktop speichern
```

그 키를 읽는 자리는 `#if DEBUG` 밖이다(`Plugin.cs:1880-1888`). 이 파일의 `#if DEBUG` 블록은 여섯인데(`82-86`, `337-346`, `752-781`, `795-840`, `1641-1650`, `1955-1959`) 그 어느 것도 이 자리를 안 덮는다.

```csharp
// Plugin.cs:1880-1888
if (IsJustPressed(_config.KeyDumpUI))
{
    if (!_uiReader.DumpFocusedAddon())
        _navigation.DumpNearbyObjects();
}
```

**띄운 창이 있으면 이 갈래로 안 온다.** `DumpFocusedAddon`이 그 창을 덤프하고 참을 돌려준다. 거짓을 돌려주는 것은 덤프할 창이 없을 때뿐이고, 그것이 곧 야외다 - 원본 주석이 그렇게 적는다.

```csharp
// UIReaderService.cs:10818-10820
/// Gibt true zurueck, wenn ein Menue/Fenster gedumpt wurde; false, wenn nichts
/// zu dumpen war (Spielwelt) - dann darf der Aufrufer die Objekt-Sonde laufen
/// lassen, ohne die Menue-Dump-Ansage zu ueberschreiben.
```

즉 **메뉴를 열어 두고 누르면 안 들리고, 필드에서 누르면 들린다.** 화면을 덤프하려고 누른 사람은 야외에서도 같은 키를 누른다.

`DumpNearbyObjects`(`:2398`)도 `#if DEBUG` 밖이다. 이 파일의 `#if DEBUG` 블록 넷 중 어느 것도 이 함수를 안 덮는다. 그 안에서 `:2433`이 `DumpMapMarkers`를 **조건 없이** 부르기 때문에 두 문장이 늘 붙어 나온다.

## 진단인데 왜 말하나 — 원본이 그렇게 정했다

이 자리를 "로그용이라 독일어여도 된다"로 읽으면 안 된다. 원본 주석이 발화의 목적을 스스로 밝힌다.

```csharp
// NavigationService.cs:2387-2389
/// Bound to the UI-dump key (Strg+F5) and to /acc objprobe. Announces the
/// count so the blind user knows the dump ran; the detail goes to the log
/// ([ObjProbe]).
```

**"so the blind user knows the dump ran"** - 상세는 로그로 보내고, 발화는 사용자에게 덤프가 돌았음을 알리려고 일부러 둔 것이다. 로그에 남기는 문장이 아니라 사용자 안내다.

## 순수한 개발용과 대비된다

같은 저장소의 진짜 진단 도구는 `#if DEBUG` 안에 있다.

| 파일 | `#if DEBUG` | 닿는 길 |
|------|-------------|---------|
| `Services/LiftProbe.cs` | 파일 전체(`1`·`197`) | `/acc lift` - 그 case도 `#if DEBUG` 안 |
| `Services/CollisionProbe.cs` | 파일 전체 | `/acc coll` - 같음 |
| `Services/NavigationService.cs`의 이 셋 | **없음**(블록 넷이 `309-354`·`2627-2643`·`2669-2678`·`4036-4067`이라 이 함수를 안 덮는다) | **기본 키 Strg+F5** |

원본은 개발용을 배포판에서 빼는 수단을 갖고 있고 실제로 쓴다. 이 자리를 안 뺀 것은 **배포판에 남길 기능으로 봤다는 뜻**이다.

주석이 적은 또 하나의 길 `/acc objprobe`는 `#if DEBUG` 안이다(`Plugin.cs:756`). 즉 **배포판에서 이 셋에 닿는 길은 기본 키 하나뿐이고, 개발자가 일부러 치는 명령 쪽이 오히려 막혀 있다.**

## 보낼 것인가 — 보낸다

[rejected.md](rejected.md)의 다섯을 하나씩 본다.

1. **코드에 한국이 안 나온다** - 넘긴다. 시그니처도 KR 시트 번호도 없다. 순수한 언어 갈림길 문제다
2. **다른 클라이언트에서도 고쳐진다** - 넘긴다. 독일어를 모르는 영어·프랑스어·일본어 사용자가 전부 같은 두 문장을 못 알아듣는다. 오히려 **한국어판보다 영어판 사용자에게 더 흔한 자리다** - 그쪽이 사용자 수가 많다
3. **원본의 결정을 뒤집지 않는다** - 넘긴다. 원본이 이미 `Loc.Pick`을 두고 형제 자리에서 쓰고 있다. 새 구조를 요구하는 것이 아니라 빠뜨린 자리를 그 장치에 태우는 것이다
4. **글섭 클라 없이 판정된다** - 넘긴다. 넷 다 소스만으로 갈린다: 기본값이 `Strg+F5`인 것(`Configuration.cs:57`), 그 자리가 `#if DEBUG` 밖인 것(`Plugin.cs:1880-1888`), 창이 없을 때 떨어지는 것(`UIReaderService.cs:10817-10820`의 계약), 리터럴이 `Loc.Pick`을 안 거치는 것. 타이밍도 레이스도 프레임 순서도 안 걸린다
5. **명백한 기존 로직의 오류다** - **넘긴다고 판정한다.** 근거는 위 두 절이다. 원본 주석이 이 발화를 `so the blind user knows`라고 못 박아 사용자 안내로 규정하고, 순수 진단은 `#if DEBUG`로 빼는 관례를 같은 저장소가 갖고 있는데 이 자리만 안 뺐다. 사용자에게 나가는 문장이 갈림길을 안 거치는 것은 이 코드베이스 자신의 규칙 위반이다

**5번이 갈릴 만한 자리다.** "이름이 Sonde(탐침)이고 내용이 개수 보고이니 진단이다, 진단은 개발자 것이라 독일어로 둔 것이 의도다"라고 읽을 수 있다. 그 읽기를 택하지 않은 까닭은 **주석이 청자를 지목하고 있어서**다 - 개발자가 아니라 `the blind user`다. 원본이 그 읽기를 고른다면 우리가 물을 것은 "그러면 왜 `#if DEBUG`가 아닌가"이고, 어느 쪽 답이 오든 이 자리는 닫힌다.

## 고칠 방향

세 리터럴을 `Loc.Pick`으로 감싼다. 다른 구조는 필요 없고, 개수와 보간 자리는 그대로 둔다.

```csharp
_tolk.SpeakInterrupt(Loc.Pick(
    $"Objekt-Sonde: {near.Count} Objekte im Log.",
    $"Object probe: {near.Count} objects in the log."));
```

`Objekt-Sonde: kein Spieler.`와 `Marker-Sonde: ...`도 같다. `/acc objprobe`로만 부르던 시절의 자리가 아니라 기본 키에 물린 자리이므로, 세 문장 다 사용자 언어로 나가야 한다.

## 우리 쪽 사정

`tools/ko-speech`가 셋을 `speech` 갈래로 잡았고, 골든이 **통과가 아니라 미해결**로 담고 있다. 옛 저장소에서 옮겨 온 근거는 `키에 안 물려 있고 채팅 명령어(/acc obj)로만 불린다`였는데 이 저장소에서 사실이 아니어서 다시 썼다(2026-09-04).

원본이 받아들이면 그 자리가 평범한 `Pick` 문장이 되어 `korean/strings.json`으로 옮겨 갈 수 있다. 받아들이지 않으면 `graft/`로 우리 트리에서만 감싸는 길이 남는다.
