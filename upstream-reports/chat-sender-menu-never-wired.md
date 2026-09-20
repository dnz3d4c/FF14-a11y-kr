# 채팅 발신자 컨텍스트 메뉴가 한 번도 배선되지 않았다

**상태**: 초안. 아래 판정대로 **보낸다**
**대상**: `FF14Accessibility/Plugin.cs:145`, `FF14Accessibility/Services/ChatPlayerService.cs`
**심각도**: 높음. 릴리스 노트가 기능으로 적었는데 키를 눌러도 아무 일도 일어나지 않는다

## 증상

`v6.08.20` 릴리스 노트가 이렇게 적는다.

```
Chat: Absender-Kontextmenü; optionale eigene Windows-Stimme pro Chat-Kanal.
```

기본 키 `Strg+Umschalt+BildAuf`가 그 기능에 걸려 있다.

```csharp
// Configuration.cs:162
public string KeyChatPlayerMenu = "Strg+Umschalt+BildAuf";          // [Chat-Absender]
```

눌러도 아무 일도 일어나지 않는다. 오류도 없고 발화도 없다. 보이지 않는 사용자에게 침묵은 "기능이 없다"와 "모드가 죽었다"를 구분해 주지 않는다.

## 왜 안 도는가

**`ChatPlayerService`가 한 번도 만들어지지 않는다.** 원본 소스 전체에서 이 이름이 나오는 곳이 셋뿐이고, 그중 어디에도 `new`가 없다.

```
Plugin.cs:145                     private readonly ChatPlayerService _chatPlayer;
Services/ChatPlayerService.cs:35  public sealed class ChatPlayerService
Services/ChatPlayerService.cs:45  public ChatPlayerService(
```

필드는 선언만 되어 있고 생성자에서도 다른 어디에서도 값이 안 들어간다. 그래서 `_chatPlayer`는 언제나 `null`이다.

**키를 읽는 자리도 없다.** `KeyChatPlayerMenu`는 `Plugin.cs`에서 딱 한 번 나오는데, 그것이 키 충돌 검사 목록이다.

```csharp
// Plugin.cs:1225
("Chat-Absender Menü",        _config.KeyChatPlayerMenu),
```

`KeybindService.DumpKeybinds`에 넘기는 목록이라 `/acc keys` 보고서에 이름이 실릴 뿐이고, 키 입력을 처리하는 분기는 만들어진 적이 없다. 그래서 **이름은 단축키 목록에 나오는데 동작은 없다** — 사용자가 목록을 읽고 그 키가 있다고 믿게 되는 모양이다.

`ChatPlayerService.cs`는 209줄이고 클래스 주석이 동작을 자세히 적고 있다. 코드가 없어서가 아니라 **아무도 그것을 부르지 않아서** 안 돈다.

## 컴파일러가 이미 말하고 있다

`Plugin`은 `sealed`이고 `partial`이 아닌 단일 파일이며 그 필드가 `private`이다. 그래서 컴파일러의 CS0169(한 번도 안 쓰인 private 필드)가 곧 전수 증거다. 지금 이 필드는 CS0169와 CS8618 둘을 낸다.

## 고칠 방향

둘 중 하나다. 어느 쪽인지는 원본의 결정이다.

1. **배선한다.** `Plugin` 생성자에서 `ChatPlayerService`를 만들고, `KeyChatPlayerMenu`를 읽는 분기를 다른 키들과 같은 자리에 더한다. `AccessibilityStrings`에 이 기능이 쓸 문장이 이미 다 있다 — `ChatPlayerNone`·`ChatPlayerMenuOpened`·`ChatPlayerNotFound`·`ChatPlayerElsewhere`·`ChatPlayerZoneUnknown`.
2. **걷어낸다.** 필드와 기본 키와 충돌 검사 목록의 줄을 빼고 릴리스 노트에서도 뺀다.

**어느 쪽이든 침묵만은 남기지 않는다.** 지금 상태는 화면에서도 로그에서도 신호가 없다.

## 기준 다섯

1. **코드에 한국이 안 나온다.** 시그니처 바이트도 `XIVLauncherKR`도 KR 시트 번호도 없다. 순수한 배선 누락이다.
2. **다른 클라이언트에서도 고쳐진다.** 언어와 무관하게 모든 사용자에게 이 기능이 없다.
3. **원본의 결정을 뒤집지 않는다.** 원본이 기능으로 적었고 코드를 209줄 썼다. 안 돌게 두기로 한 결정의 흔적이 없다.
4. **글섭 클라 없이 판정된다.** 소스를 읽어서 나온다 — `new`가 없고 키를 읽는 분기가 없다. 돌려 봐야 아는 것이 하나도 없다.
5. **명백한 기존 로직의 오류다.** 코드를 읽은 사람이 "이건 버그다"에서 갈리지 않는다.

## 우리 쪽 사정

한국어판은 조립할 때 `-warnaserror`로 빌드하므로 CS0169와 CS8618이 빌드를 세운다. 그래서 `graft/rules.json`의 `plugin-drop-dead-chatplayer-field`가 그 필드 선언과 앞줄 주석을 우리 트리에서만 뺀다. 항상 `null`이고 아무도 안 읽으므로 동작이 안 바뀐다.

**우리가 배선하지는 않는다.** 원본이 기능으로 정한 것이고 어느 쪽으로 닫을지는 원본이 정할 일이다. 원본이 나중에 그 필드를 실제로 배선하면 우리 규칙의 앵커가 안 맞아 조립이 규칙 이름을 대고 멈춘다.
