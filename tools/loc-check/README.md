# loc-check — 설치 프로그램 문구가 한국어로 나가는지 지킨다

`tools/assemble`이 **모드**의 발화를 지킨다면, 이쪽은 **설치 프로그램**을 본다. 둘로 나눈 이유는 하나다 — 조립의 대상은 `FF14Accessibility/`(플러그인)이고, `Installer/`는 자체 사전(`Installer/Loc.cs`)이 세 언어를 들고 있어 대장을 안 거친다고 명시적으로 빼 두었다(`tools/assemble/assemble.py:50-52`). 그래서 설치 프로그램의 한국어는 어느 검사에도 안 걸린다.

## 왜 생겼나

`Installer/Loc.cs`의 `Get`은 세 번 조용하다.

- 현재 언어에 키가 없으면 **영어로 떨어진다**(`Loc.cs:29`). 로그도 예외도 없다
- 영어에도 없으면 **키 이름을 그대로 돌려준다**. 사용자는 `InstallerAssetMissing` 같은 식별자를 듣는다
- 키가 있어도 값이 비면 **접두만 붙은 빈 줄**이 나간다. 실제로 `ConfigNotExist4`가 그 모양이었다

셋 다 오류가 아니라서, 드러나는 자리는 사용자 화면뿐이다.

**2026-09-04 실측으로 새는 자리는 0건이었다** — 부르는 키가 전부 한국어를 갖고 있었다. 그래서 지금 못박는다. 이 검사가 막는 것은 이미 난 사고가 아니라 **다음에 영어 키만 더하는 순간**이다.

지금 몇 개인지는 여기 적지 않는다. 도구가 돌 때마다 세어서 말한다 — 손으로 옮겨 적은 숫자는 낡는다.

## 판정 대상은 조립 산출물이다

설치 프로그램 소스 아홉이 세 군데에 흩어져 있다.

| 트리 | 파일 |
|------|------|
| `replace/Installer/` | `InstallerService.cs`, `Loc.cs`, `LanguageDialog.cs` |
| `kr/Installer/` | `KrCheck.cs`, `KrProfile.cs` |
| `upstream/Installer/` | `FF14AccessibilityInstaller.csproj`, `MainForm.cs`, `Program.cs`, `SelfUpdate.cs` |

`Loc.Get("키")` 호출은 **원본 파일에도 있다.** 2026-09-04 실측으로 `MainForm.cs`와 `SelfUpdate.cs`가 17개 키를 부르고, 그중 **15개는 그 둘만 부른다.** 한국어 쪽 트리만 보면 그 15개가 "안 불리는 키"로 분류되고, 죽은 키 골든이 조용히 통과시킨다.

`kr/Installer/`의 둘은 `Loc.Get`을 한 번도 안 부른다. 그래도 조립 트리를 보는 이유는 위의 원본 파일 때문이다.

그래서 `SOURCE_ROOT`는 `build/Installer`다. **조립 결과가 실제로 나갈 트리이고 판정 대상은 그것이다.**

조립을 안 돌렸으면 도구가 멈춘다. 소스가 없으면 부르는 키도 0개가 되어 아래 검사가 전부 통과하는데, 그 침묵을 초록으로 내보내지 않는다.

    uv run python tools/assemble/assemble.py

## 무엇을 보나

| 검사 | 무엇이 걸리나 | 사용자가 겪는 것 |
|------|--------------|-----------------|
| 번역 없음 | 부르는 키에 한국어가 없다 | 영어 문장이 나간다 |
| 정의 없음 | 부르는 키가 어느 사전에도 없다 | **키 이름**이 그대로 나간다 |
| 빈 값 | 어느 언어든 값이 비었다 | `경고: ` 한 줄만 나간다 |
| 맨 리터럴 | `Loc.Get`을 안 거치는 문자열 | 어느 언어로도 안 갈린다 |
| 죽은 키 | 번역 없는 키가 골든보다 늘었다 | (아직 아무 일도 안 일어난다) |
| 서식 자리 | 같은 키인데 언어마다 `{0}` 집합이 다르다 | 넘긴 값이 **버려진 채로** 나간다 |

**서식 자리만 실제로 난 사고다.** `KrWaitingForDalamud`가 독일어·영어에는 `{0}`을 갖고 있는데 한국어에만 통째로 빠져 있었고, `InstallerService`가 넘긴 대기 시간 `15`가 버려진 채 배포됐다. 나머지 검사와 달리 이건 예방이 아니라 **이미 난 것을 잡은 것**이다. 사전 셋을 나란히 놓고 보기 전에는 사람 눈에 안 잡히는 부류다.

번호가 어긋나는 것도 같이 잡는다 — 개수가 같아도 `{0}`과 `{1}`이 바뀌면 다른 값이 박힌다. `{{`는 C#에서 리터럴 중괄호라 자리로 세지 않는다. 한 사전에만 있는 키는 나란히 놓을 상대가 없어서 이 갈래가 보지 않는다(죽은 키가 거기 해당한다).

**맨 리터럴은 두 갈래로 잡는다.** 움라우트(`[äöüßÄÖÜ]`)를 가진 것은 어디 있든 잡고, 그 밖에는 사람에게 말하는 호출(`Info`/`Warn`/`Error`)의 인자일 때만 잡는다. 라틴 문자만으로는 문장인지 파일 이름인지 안 갈려서, **호출 자리**로 가른다. 움라우트를 쓰는 이유는 원본이 독일어로 개발되기 때문이다 — 그 글자가 남아 있으면 그 자리는 번역을 안 거친 독일어 문장이다.

글자가 하나도 없는 리터럴은 안 잡는다. `Info("  " + path)`의 `"  "`는 들여쓰기지 문장이 아니다.

## 죽은 키는 골든에 담는다

영어 사전에만 있고 아무도 안 부르는 키가 28개 있다. 글로벌 설치 프로그램에서 온 `XivLauncher` 잔재라 한국어를 지어낼 이유가 없다. 지우는 것은 원본 소스를 건드리는 일이라 여기서 안 하고, **늘어나는 것만 막는다.**

그 키를 누가 부르기 시작하면 골든이 아니라 `번역 없음`으로 걸린다 — 죽은 키의 정의가 "안 불린다"이기 때문이다.

## 주석은 남의 것을 쓴다

문자열 안의 `//`를 주석으로 읽으면 안 된다. 안내 문구에 `https://goatcorp.github.io/`가 들어 있어서, 그 줄이 통째로 지워지면 멀쩡한 값이 비었다고 잡힌다. 이미 `tools/assemble/scanner.py`의 `strip_comments`가 그 문제를 풀어 놨으므로 가져다 쓴다.

## 한계 — 이 검사가 안 보는 자리

**초록이라고 "안내 문구가 다 한국어다"가 아니다.** 아래는 이 도구가 판정하지 않는 것이고, 각각 무엇으로 확인하는지 같이 적는다. 한계를 적어 두는 것만으로는 모자라서 **확인 명령까지** 둔다.

### 1. 맨 리터럴은 세 호출만 본다

`Info`·`Warn`·`Error`의 인자만 본다(움라우트를 가진 것은 예외로 어디서든 잡는다). **사용자에게 문자열이 닿는 길은 그 셋만이 아니다.**

- `MessageBox.Show(...)` — 대화 상자
- `Text = ...` — 창 제목과 버튼 글자
- `AccessibleName = ...` — **스크린리더가 읽는 이름**
- `Console.WriteLine(...)` — `--check`/`--install`의 출력

2026-09-04 기준 걸리는 자리는 **한 곳**이다 — `KrCheck.cs:118`의 `Console.WriteLine("base directory: " + AppContext.BaseDirectory)`. `--check`가 내는 진단 줄이라 사용자 안내가 아니고, 결함이 아니다. 나머지는 전부 `Loc.Get`을 거치고 있다. **우연이 아니라 지금까지 그렇게 써 온 것뿐이고, 이 검사가 그걸 지키지는 않는다.** `AccessibleName = "직접 쓴 문자열"`이 들어와도 조용하다.

확인 (`Loc.Get`을 안 거치고 대입된 자리를 센다):

uv run python -c "import re,sys;sys.path.insert(0,'tools/assemble');import scanner;from pathlib import Path;p=Path('build/Installer');rx=re.compile(r'(MessageBox\.Show|Console\.WriteLine)\s*\(\s*\"|(?<![A-Za-z0-9_.])(Text|AccessibleName|AccessibleDescription)\s*=\s*\"');print([(c.name,m.group(0)) for c in p.rglob('*.cs') if c.name!='Loc.cs' for m in rx.finditer(scanner.strip_comments(c.read_text(encoding='utf-8')))])"

위의 한 곳 말고 다른 것이 나오면 그 자리를 눈으로 본다.

### 2. 죽은 키 골든은 "지금 안 불린다"만 말한다

**골든이 구멍이 되지는 않는다.** 골든에 담긴 키에 호출부가 생기면 `번역 없음`과 `골든에만 남은 키` 두 갈래로 걸린다(합성 소스로 실증했다). 통과시키지 않는다.

다만 골든이 **말하지 않는 것**이 둘이다.

- **그 키를 지워야 하는지 아닌지.** 28개는 글로벌 설치 프로그램 잔재라는 한 문장으로 묶여 있을 뿐, 항목마다 왜 남았는지가 없다
- **영어 문구가 맞는지.** 이 도구는 키가 있나 없나만 본다

확인: `tools/loc-check/golden/dead-keys.json`을 열어 28개를 눈으로 훑는다.

### 3. `Loc.Get(리터럴이 아닌 것)`은 못 센다

키 집계는 `Loc.Get("리터럴")`만 잡는다. 변수나 조건식을 넘기면 **그 키는 "안 불린다"로 분류되고**, 한국어가 없어도 죽은 키 골든이 통과시킨다. 조용히 새는 유일한 갈래다.

**2026-09-04 기준 1건 있다.** `InstallerService.cs:1892`가 조건식을 넘긴다.

    Info(Loc.Get(existing != null ? "KrProfileEntryUpdated" : "KrProfileEntrySeeded",
        internalName, workingId.ToString()));

두 키는 리터럴로 적혀 있는데도 `Loc.Get(` 바로 뒤가 아니라서 집계에서 빠진다. **지금은 둘 다 한국어를 갖고 있어 새는 것이 없다.** 앞으로 이 자리에 키를 더하면 이 검사가 아무 말도 안 한다는 것만 알고 있으면 된다.

확인 (0이 아니면 그만큼 집계에서 빠진 것이다):

uv run python -c "import re,sys;sys.path.insert(0,'tools/assemble');import scanner;from pathlib import Path;p=Path('build/Installer');print(sum(len(re.findall(r'Loc\.Get\(\s*(?!\")',scanner.strip_comments(c.read_text(encoding='utf-8')))) for c in p.rglob('*.cs')))"

### 4. 사전 파싱은 정규식이라 모양에 기댄다

`[English] = new Dictionary<string, string> { ... }` 꼴을 찾고, 그 안에서 `["키"] =` 꼴을 센다. `Loc.cs`가 초기화 구문을 바꾸면 못 읽는다.

**다만 못 읽는다고 조용해지지는 않는다.** 합성 소스로 확인했다.

- 사전 블록 자체를 못 찾으면 → `ValueError`로 죽는다
- 블록은 찾고 항목 모양만 바뀌면 → 사전이 0개가 되고, 부르는 키가 **전부 `정의 없음`으로** 걸린다

조용해지는 경우는 하나뿐이다 — **사전과 호출부를 동시에 못 읽을 때**다(`Loc.Get` 표기까지 바뀌는 경우). 그때는 0 대 0이라 아무 말도 안 한다. 그 자리를 `test_실물에서_사전을_실제로_읽는다`가 막는다: 한국어 100개 미만이거나 부르는 키 100개 미만이면 빨개진다. **이 테스트를 지우면 위 검사 넷이 조용히 무의미해진다.**

### 5. 모드 쪽은 안 본다

`Installer/`만 본다. 플러그인(`FF14Accessibility/`)의 발화는 `tools/assemble`이 갖는다. 두 검사망은 겹치지 않으므로, 어느 쪽이 초록이라고 다른 쪽을 말해 주지 않는다.

## 쓰는 법

    uv run python tools/assemble/assemble.py            # 먼저 조립한다
    uv run python tools/loc-check/loc_check.py          # 대조
    uv run python tools/loc-check/loc_check.py --write  # 죽은 키 골든 갱신

## 테스트

    uv run python -m pytest tools/loc-check -q

실물 대조 넷은 `build/Installer`가 있을 때만 돈다. 조립 전이면 건너뛴다 — 도구 자신이 그때 멈추는 것과는 다른 일이다.
