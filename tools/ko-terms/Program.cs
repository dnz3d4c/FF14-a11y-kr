// 게임 데이터에서 한국어 UI 낱말을 뽑는다.
//
// 왜 필요한가: 모드가 말하는 낱말과 게임 화면에 뜨는 낱말이 다르면 사용자가
// 이름을 두 개 외워야 한다. 그래서 게임이 쓰는 말을 그대로 써야 하는데
// **지어내면 안 된다.** 이 저장소는 이미 한 번 당했다 - `Aetheryte`를
// "에테라이트"라고 스킬에 결정으로 박아 놨는데 로그·덤프 전체에서 그 표기가
// 0건이었다.
//
// 로그를 뒤지는 방법은 그 화면에 들어가 본 적이 있어야 한다. 이 도구는 게임을
// 켜지 않고 sqpack에서 직접 읽으므로 그 제약이 없다.
//
// 찾는 방식이 이 도구의 핵심이다. **행 번호로 잇는다.** 같은 행이 언어마다
// 같은 문자열이므로, 아는 언어로 찾아 행을 잡고 그 행의 한국어를 읽는다.
// 한국어를 짐작해서 찾지 않는다 - 그러면 짐작이 답이 되어 버린다.
//
// 시트가 넷이다. UI 문자열은 Addon에 있지만 기술·소환수·상태 이름은 거기
// 없고 각각 Action·Pet·Status에 있다. **Addon에서 0건인 것은 "게임에 없다"가
// 아니라 "그 시트 밖"이다.** 열 이름도 시트마다 다르다 - Addon만 `Text`고
// 나머지 셋은 `Name`이다 (Lumina.Excel.Sheets의 형 정의를 반사로 확인).
//
// 사용법:
//     dotnet run --project tools\ko-terms\koterms.csproj -c Release -- <모드> [인자]
//
//     langs                이 sqpack에 어떤 언어가 들어 있나
//     find <낱말>          아는 언어로 찾아 한국어를 나란히 본다
//     row <번호>           행 번호로 바로 본다
//     dump <디렉토리>      전 행을 TSV로
//
//     --sheet <이름>       Addon(기본) | Action | Pet | Status | all

using System.Text;
using Lumina;
using Lumina.Data;
using Lumina.Excel;
using Lumina.Excel.Sheets;
// Lumina.Excel.Sheets.Action이 System.Action과 이름이 겹친다.
using ActionSheet = Lumina.Excel.Sheets.Action;

Console.OutputEncoding = Encoding.UTF8;

const string GameRoot = @"C:\Program Files (x86)\FINAL FANTASY XIV - KOREA";

var sqpack = Path.Combine(GameRoot, "game", "sqpack");
if (!Directory.Exists(sqpack))
{
    Console.Error.WriteLine($"게임 데이터가 없다: {sqpack}");
    Console.Error.WriteLine("  설치 경로는 tools/ko-terms/README.md.");
    return 2;
}

// 체크섬 검사를 끄는 것은 추측이 아니다. KR 시트는 Lumina의 글로벌 기준
// 스키마와 체크섬이 어긋나고, KR Dalamud 언어 패치도 같은 이유로 이걸 끈다.
GameData game;
try
{
    game = new GameData(sqpack, new LuminaOptions
    {
        PanicOnSheetChecksumMismatch = false,
        DefaultExcelLanguage = Language.Korean,
    });
}
catch (Exception ex)
{
    Console.Error.WriteLine($"게임 데이터를 못 열었다: {ex.Message}");
    return 2;
}

var known = new List<Sheet>
{
    Make<Addon>("Addon", r => r.Text.ExtractText()),
    Make<ActionSheet>("Action", r => r.Name.ExtractText()),
    Make<Pet>("Pet", r => r.Name.ExtractText()),
    Make<Status>("Status", r => r.Name.ExtractText()),
};

// `--sheet`는 모드 앞뒤 어디에 와도 된다. 떼어 내고 나머지를 예전처럼 읽는다.
var argv = new List<string>(args);
var wantedSheet = "Addon";
for (var i = 0; i < argv.Count; i++)
{
    if (argv[i] != "--sheet") continue;
    if (i + 1 >= argv.Count)
    {
        Console.Error.WriteLine("--sheet 다음에 시트 이름을 달라.");
        return 2;
    }

    wantedSheet = argv[i + 1];
    argv.RemoveRange(i, 2);
    break;
}

List<Sheet> selected;
if (string.Equals(wantedSheet, "all", StringComparison.OrdinalIgnoreCase))
{
    selected = known;
}
else
{
    selected = known
        .Where(s => string.Equals(s.Name, wantedSheet, StringComparison.OrdinalIgnoreCase))
        .ToList();
    if (selected.Count == 0)
    {
        var names = string.Join(", ", known.Select(s => s.Name));
        Console.Error.WriteLine($"모르는 시트: {wantedSheet} (아는 것: {names}, all)");
        return 2;
    }
}

// 어느 언어가 실제로 들어 있는지는 클라이언트마다 다르다. 한국 클라이언트가
// 영어를 같이 담고 있는지는 **확인해 봐야 아는 것**이라 하드코딩하지 않는다.
var candidates = new[]
{
    Language.Korean, Language.English, Language.Japanese,
    Language.German, Language.French,
};

var available = new List<Language>();
foreach (var language in candidates)
{
    if (selected.Any(sheet => CountOf(sheet, language) > 0)) available.Add(language);
}

if (available.Count == 0)
{
    var names = string.Join(", ", selected.Select(s => s.Name));
    Console.Error.WriteLine($"{names} 시트를 어떤 언어로도 못 읽었다.");
    return 1;
}

var mode = argv.Count > 0 ? argv[0] : "langs";

switch (mode)
{
    case "langs":
        Console.WriteLine($"sqpack: {sqpack}");
        foreach (var sheet in selected)
        {
            Console.WriteLine($"  {sheet.Name}");
            foreach (var language in available)
            {
                var count = CountOf(sheet, language);
                if (count > 0) Console.WriteLine($"    {language}\t{count}행");
            }
        }

        return 0;

    case "find":
        if (argv.Count < 2) { Console.Error.WriteLine("찾을 낱말을 달라."); return 2; }
        return Find(argv[1]);

    case "row":
        if (argv.Count < 2 || !uint.TryParse(argv[1], out var wanted))
        { Console.Error.WriteLine("행 번호를 달라."); return 2; }
        Show(wanted);
        return 0;

    case "dump":
        if (argv.Count < 2) { Console.Error.WriteLine("출력 디렉토리를 달라."); return 2; }
        return Dump(argv[1]);

    default:
        Console.Error.WriteLine($"모르는 모드: {mode}");
        return 2;
}

// 그 시트를 그 언어로 못 읽는 것은 오류가 아니다. 없는 조합이 그냥 있다.
int CountOf(Sheet sheet, Language language)
{
    try { return sheet.Count(language); }
    catch { return 0; }
}

string TextAt(Sheet sheet, Language language, uint rowId)
{
    try { return sheet.TextAt(language, rowId); }
    catch { return ""; }
}

void Show(uint rowId)
{
    Console.WriteLine($"행 {rowId}");
    foreach (var sheet in selected)
    foreach (var language in available)
    {
        var text = TextAt(sheet, language, rowId);
        if (!string.IsNullOrWhiteSpace(text))
            Console.WriteLine($"  {sheet.Name,-8} {language,-8} {text}");
    }
}

int Find(string query)
{
    // 한국어 말고 다른 언어에서 찾는다. 한국어로 찾으면 짐작한 낱말이 그대로
    // 답이 되어 버려서, 확인이 아니라 자기 확인이 된다.
    var searchable = available.Where(l => l != Language.Korean).ToList();
    if (searchable.Count == 0)
    {
        Console.Error.WriteLine(
            "이 sqpack에는 한국어밖에 없다. 행 번호를 아는 경우에만 `row`로 볼 수 있다.");
        Console.Error.WriteLine(
            "  글로벌 클라이언트가 있으면 거기서 행 번호를 잡아 여기서 그 행을 읽는다.");
        return 1;
    }

    var hits = new SortedSet<uint>();
    foreach (var sheet in selected)
    foreach (var language in searchable)
    {
        foreach (var (rowId, text) in sheet.Rows(language))
        {
            if (!string.IsNullOrEmpty(text)
                && text.Contains(query, StringComparison.OrdinalIgnoreCase))
                hits.Add(rowId);
        }
    }

    if (hits.Count == 0)
    {
        Console.WriteLine($"'{query}' 없음. 못 찾았으면 못 찾았다고 적어라 - 지어내지 않는다.");
        return 1;
    }

    Console.WriteLine($"'{query}' {hits.Count}행");
    foreach (var rowId in hits) Show(rowId);
    return 0;
}

int Dump(string directory)
{
    Directory.CreateDirectory(directory);
    foreach (var sheet in selected)
    foreach (var language in available)
    {
        if (CountOf(sheet, language) == 0) continue;

        // 파일 이름에 시트가 들어가야 시트끼리 안 섞인다.
        var path = Path.Combine(directory, $"{sheet.Name.ToLowerInvariant()}-{language}.tsv");
        using var writer = new StreamWriter(path, false, new UTF8Encoding(false));
        writer.NewLine = "\n";
        writer.WriteLine("row\ttext");
        foreach (var (rowId, text) in sheet.Rows(language))
        {
            if (string.IsNullOrWhiteSpace(text)) continue;
            // 탭과 줄바꿈은 TSV를 깨므로 눈에 보이게 바꿔 둔다.
            writer.WriteLine($"{rowId}\t{text.Replace("\t", "\\t").Replace("\n", "\\n").Replace("\r", "")}");
        }

        Console.WriteLine($"  {path}");
    }

    return 0;
}

// 시트를 이름으로 고를 수 있게 감싼다. 열 이름이 시트마다 달라서(Addon은
// `Text`, 나머지는 `Name`) 뽑는 함수를 시트마다 같이 들고 다닌다.
Sheet Make<T>(string name, Func<T, string> text) where T : struct, IExcelRow<T>
{
    IEnumerable<(uint RowId, string Text)> Rows(Language language)
    {
        var sheet = game.GetExcelSheet<T>(language);
        if (sheet is null) yield break;
        foreach (var row in sheet) yield return (row.RowId, text(row));
    }

    return new Sheet(
        name,
        language => game.GetExcelSheet<T>(language) is { } sheet ? sheet.Count : 0,
        (language, rowId) =>
            game.GetExcelSheet<T>(language)?.GetRowOrDefault(rowId) is { } row ? text(row) : "",
        Rows);
}

internal sealed record Sheet(
    string Name,
    Func<Language, int> Count,
    Func<Language, uint, string> TextAt,
    Func<Language, IEnumerable<(uint RowId, string Text)>> Rows);
