# 키 도움말이 없앤 채집 수첩 메뉴를 다시 안내한다

**상태**: 초안. 아래 판정대로 **보낸다**
**대상**: `FF14Accessibility/Services/AccessibilityStrings.cs`의 `HelpFull` (v6.08.32 `f5cdf47`에서 생겼고 v6.08.129까지 그대로다)
**심각도**: 낮음. 도움말이 없는 키를 안내한다

## 증상

v6.08.32가 `HelpFull`에 두 언어로 한 줄을 더했다. v6.08.118 병합 이후 러시아어 문장(`:3002`)도 같은 내용을 옮겼다.

```
"Strg+Nummernblock 2, Sammel-Notizbuch: Miner, Gärtner, Fischer. Nummernblock 0 läuft zum Fundort. " +
"Ctrl+Numpad 2, gathering notebook: Miner, Botanist, Fisher. Numpad 0 walks to the location. " +
"Ctrl+Numpad 2, журнал собирателя: рудокоп, ботаник, рыбак. Numpad 0 ведёт к месту находки. " +
```

그런데 원본 `STATUS.md:689`(v6.08.129)가 그 메뉴를 없앴다고 적는다.

```
>>> ÄNDERUNG: SpokenMenu (Strg+Numpad2, `/acc gatherlog`, Auto-Lauf) entfernt.
```

## 왜 결함인가

지금 소스에 `Strg+Nummernblock 2`로 채집 수첩을 여는 분기가 없다. `Numpad2` 입력은 프로필 커서·기술 메뉴·DC 지도 탐색(v6.08.129 `Plugin.cs:1827`, `:1854`, `:3205`, `:3235`)에만 쓰이고, `Configuration.cs`에 그 조합을 담은 키 설정도 없다. `/acc gatherlog`도 사라지고 `gatherlogprobe`(`Plugin.cs:1250`)만 남았는데 그것도 `#if DEBUG` 안이라 배포판에는 없다. 도움말을 듣고 그 키를 누르면 아무 일도 없거나 다른 동작이 나간다.

## 기준 다섯

1. **코드에 한국이 안 나온다.** 통과.
2. **다른 클라이언트에서도 고쳐진다.** 통과. 세 언어 문장이 같이 틀렸다.
3. **원본의 결정을 뒤집지 않는다.** 통과. 없앤 것은 원본의 결정이고 도움말만 그것을 못 따라갔다.
4. **글섭 클라 없이 판정된다.** 통과. 소스와 `STATUS.md`를 읽어서 나온다.
5. **명백한 기존 로직의 오류다.** 통과. 없는 키를 안내한다.

## 우리 쪽 사정

v6.08.129부터 조립 도구가 `HelpFull`을 읽어서 한국어로 옮겼다. 그 줄도 원문대로 옮겼다 — 우리가 문장을 빼지 않는다. 그래서 한국어판 사용자도 없는 키를 안내받는다.

## 출처

2026-09-25 6.8.32.0 릴리스 노트를 쓰다가 찾았다.
