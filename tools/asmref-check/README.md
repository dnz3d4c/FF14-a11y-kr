# asmref-check — 플러그인이 부르는 멤버가 실제로 있는지 본다

플러그인 DLL이 참조하는 멤버가 **한국 클라이언트용 Dalamud가 실제로 깔아 둔 어셈블리에 존재하는지**를 게임을 켜지 않고 판정한다.

한국 클라이언트용 Dalamud는 공식 15.0.3.2를 IL 패치한 것이고 FFXIVClientStructs를 7.55 계열에서 7.51로 낮춰 싣는다(`docs/dev/dalamud-refs.md`). 글로벌용으로 빌드된 플러그인은 이 차이 때문에 **적재는 되는데 호출 시점에 MissingMethodException으로 죽을** 수 있다. 이 도구는 그 위험을 사전에 거른다.

## 판정하는 것과 못 하는 것

판정한다 — 어셈블리 메타데이터 수준의 바인딩. 플러그인의 TypeReference / MemberReference 테이블을 전수 열거해서, 참조하는 타입과 멤버가 실제 어셈블리에 이름·인자 개수·시그니처까지 맞게 있는지 본다. 즉 "적재와 JIT가 성립하는가"에 답한다.

판정하지 못한다 — 런타임 주소. FFXIVClientStructs는 멤버 함수 주소를 시그니처 스캔으로 잡고 필드 오프셋은 구조체 레이아웃에 박혀 있다. 클라이언트 바이너리가 다르면 메타데이터에 아무 흔적 없이 런타임에 틀린 주소가 나온다. **"잡은 주소가 맞는가"는 이 도구 밖이다.**

## 쓰는 법

**저장소 루트에서** 실행한다. 이 도구 자신은 따로 빌드할 필요가 없다 — `dotnet run`이 빌드까지 한다.

`PATH`의 `dotnet`은 이 컴퓨터에서 런타임만 있고 SDK가 없어서, SDK가 든 쪽을 지목해야 한다(`tools/ko-terms/README.md`도 같은 이유로 그렇게 한다).

판정 대상은 조립한 트리를 빌드한 결과다. 먼저 둘을 돌린다. **Debug로 빌드하지 않는다** — 원본 csproj의 `DeployToDevFolder`가 Debug 조건이라 결과가 개발용 플러그인 자리로 자동 복사된다(`docs/dev/dalamud-refs.md`).

    uv run python tools/assemble/assemble.py

"C:\Users\advck\scoop\apps\dotnet-sdk\current\dotnet.exe" build -c Release build\FF14Accessibility\FF14Accessibility.csproj

**순서를 거꾸로 하면 안 된다.** 조립은 `build/`를 다시 만들기 때문에, 빌드해 둔 뒤에 조립을 또 돌리면 판정 대상 DLL이 사라진다. 그때는 `DirectoryNotFoundException`으로 죽으므로 조용히 틀린 답이 나오지는 않는다.

그다음 대조한다. 참조 어셈블리 디렉토리는 `DALAMUD_HOME`이고, 그 값이 어디를 가리켜야 하는지는 `docs/dev/dalamud-refs.md`가 갖는다. 아래는 **Git Bash 기준**이다.

"$USERPROFILE\scoop\apps\dotnet-sdk\current\dotnet.exe" run -c Release --project tools/asmref-check -- build/FF14Accessibility/bin/Release/net10.0-windows/FF14Accessibility.dll "$DALAMUD_HOME"

특정 어셈블리만 보려면 뒤에 `--only FFXIVClientStructs` 또는 쉼표로 여러 개를 붙인다. 어셈블리별 검사 건수를 따로 뽑을 때 쓴다.

## 검사 대상 선정

참조 디렉토리에 같은 이름의 `.dll`이 있는 어셈블리만 본다. BCL(`System.*`)은 거기 없으니 자동으로 빠진다.

플러그인이 자기 디렉토리에 사본을 들고 오는 의존성도 뺀다. Dalamud 플러그인 로더가 플러그인 디렉토리를 먼저 보기 때문에 런타임엔 그 사본이 쓰이고, Hooks 쪽 버전과 대조하면 헛경보가 난다.

**2026-09-04 기준 우리 플러그인에서는 이 배제가 아무것도 안 뺀다.** 같이 나가는 것이 `NAudio*`·`Tolk`·`System.Speech`·`nvdaControllerClient64`인데 Hooks에는 그 이름이 하나도 없다. 규칙이 도는지는 아래 (b)가 확인한다.

단 플러그인이 참조 디렉토리 **안에** 있으면(자기 정합성 검사) 사본이란 개념이 없으므로 이 배제를 끈다. `--only`를 주면 배제 규칙보다 우선한다.

## 판정 종류

| 판정 | 뜻 |
|------|-----|
| `MISSING TYPE` | 타입 자체가 없다. 그 타입을 쓴 멤버 이름을 같이 찍는다 |
| `MISSING MEMBER` | 타입은 있는데 그 이름의 멤버가 하나도 없다 |
| `ARITY MISMATCH` | 이름은 있는데 인자 개수가 맞는 오버로드가 없다. 기대 개수와 실제 후보 개수를 같이 찍는다 |
| `SIGNATURE DIFF` | 이름·개수는 맞는데 파라미터 타입이나 반환 타입이 다르다. **경고** |

출력은 어셈블리별로 묶고 헤더에 참조 버전과 실제 버전을 같이 찍는다. 문제 없으면 `(no issues)`, 마지막에 `SUMMARY` 한 줄.

## 종료 코드

| 코드 | 조건 |
|------|------|
| 0 | 문제 없음, 또는 `SIGNATURE DIFF`만 있음 |
| 1 | `MISSING TYPE` / `MISSING MEMBER` / `ARITY MISMATCH`가 하나라도 있음 |
| 2 | 인자 부족 (용법 오류) |

`SIGNATURE DIFF`를 0으로 두는 이유: 바인딩을 실제로 깨뜨리는 건 타입·멤버 부재와 인자 개수 불일치다. 시그니처 문자열 차이는 이 도구의 짧은 이름 비교가 만들어내는 잡음일 수 있어 사람이 보고 판단할 몫으로 남긴다.

## 도구가 조용한 게 아니라는 것을 먼저 보인다

이 도구는 **전부 통과로 나올 때 그게 진짜 안전인지 도구가 안 도는 것인지 구분되지 않으면 쓸모가 없다.** 그래서 양쪽 방향의 대조군을 둘 다 둔다. 도구를 고친 뒤에는 반드시 둘 다 다시 돌린다.

### (a) 울리기는 하는가 — 음성 대조군

멤버를 일부러 뺀 어셈블리 두 판을 `tests/`에 두고 실제로 돌린다.

- `tests/v1/` — 구판. `tests/client/`가 이걸 보고 컴파일된다
- `tests/v2/` — 신판. `Gone` 타입 삭제, `Foo.Baz` 필드 삭제, `Foo.Bar` 인자 1→2, `Foo.Keep` 인자 `string`→`object`. `Foo.Ptr`(포인터 인자)와 `Nest.Inner.Deep`(중첩 타입)은 안 건드린다
- `tests/client/` — v1으로 컴파일해 참조 테이블만 뽑아낸다. 실행하지 않는다

저장소 루트에서 한 줄로 돌린다.

DN="$USERPROFILE\scoop\apps\dotnet-sdk\current\dotnet.exe"; T=tools/asmref-check/tests; "$DN" build -c Release -v q --nologo $T/v1 && "$DN" build -c Release -v q --nologo $T/client && "$DN" build -c Release -v q --nologo $T/v2 && "$DN" run -c Release --project tools/asmref-check -- $T/client/bin/Release/net10.0/Client.dll $T/v2/bin/Release/net10.0 --only StubLib

2026-09-04 실측 출력이다.

```
# StubLib ref=1.0.0.0 actual=1.0.0.0
  MISSING TYPE    Stub.Gone    members: Poof
  MISSING MEMBER  Stub.Foo.Baz    want field Int32
  ARITY MISMATCH  Stub.Foo.Bar    want 1 params [Void Bar(Int32)]    actual [2]
  SIGNATURE DIFF  Stub.Foo.Keep    ref: Void Keep(String)    actual: Void Keep(Object)

SUMMARY: 7 checked, 1 missing-type, 1 missing-member, 1 arity, 1 sig-diff
```

종료 코드는 1이다. 4종이 각각 한 건씩 울리고, 안 바꾼 `Foo.Ptr`와 `Nest.Inner.Deep`은 조용하다 — 즉 무조건 울리는 것도 아니다. `--only`를 쓰는 이유는 client 디렉토리에 StubLib 사본이 복사되기 때문이다. 자기 번들 배제 규칙에 걸리는 걸 `--only`가 덮는다.

### (b) 헛울리지는 않는가 — 자기 정합성

Hooks 디렉토리의 `Dalamud.dll`을 **같은 디렉토리에 대고** 검사한다.

"$USERPROFILE\scoop\apps\dotnet-sdk\current\dotnet.exe" run -c Release --project tools/asmref-check -- "$DALAMUD_HOME\Dalamud.dll" "$DALAMUD_HOME"

어셈블리가 자기와 함께 배포된 의존성을 못 찾을 리 없으므로, **여기서 나오는 것은 전부 오탐이다.** 무엇보다 `Dalamud.dll` 자신이 FFXIVClientStructs 7.55.1.8875를 참조하는데 실제로 깔린 건 7.51.0.8667이다 — 7.55→7.51 다운그레이드를 가로지르는 참조가 전부 해석되는지 보는 것이라 이 프로젝트의 관심사와 정확히 겹친다.

2026-09-04 실측으로 `3763 checked, 0 missing-type, 0 missing-member, 0 arity, 0 sig-diff`였다.

**이 대조군이 우리 플러그인에 기대지 않는다는 게 중요하다.** 우리 것이 아직 게임에서 안 돌아 봤어도 (b)는 그대로 성립한다.

교정에서 실제로 잡아낸 오탐 2건은 이렇게 나왔다.

- 플러그인 디렉토리 == 참조 디렉토리일 때 자기 번들 배제 규칙이 참조 디렉토리 전체를 배제해 `0 checked`가 됐다. (b)가 아니었으면 못 잡는다
- 함수 포인터 타입에서 리플렉션 쪽 `Type.Name`이 빈 문자열이라 88건이 가짜 `SIGNATURE DIFF`로 잡혔다. ClientStructs의 `*VirtualTable` / `MemberFunctionPointers`가 전부 이 형태다

**검사 결과를 0건으로 보고할 때는 이 대조군 둘을 같이 돌린 사실을 붙인다.**

## 지금 결과

2026-09-04 실측. 조립 → Release 빌드 → 위 명령 순으로 돌렸다.

```
# Dalamud ref=15.0.3.2 actual=15.0.3.2                        (no issues)
# FFXIVClientStructs ref=7.51.0.8667 actual=7.51.0.8667       (no issues)
# InteropGenerator.Runtime ref=1.0.0.0 actual=1.0.0.0         (no issues)
# Lumina ref=7.0.0.0 actual=7.0.0.0                           (no issues)
# Lumina.Excel ref=7.0.0.0 actual=7.0.0.0                     (no issues)

SUMMARY: 1072 checked, 0 missing-type, 0 missing-member, 0 arity, 0 sig-diff
```

참조 버전과 실제 버전이 다섯 다 같다. 글로벌용 빌드였다면 FFXIVClientStructs가 `ref=7.55.x actual=7.51.x`로 갈렸을 자리다.
