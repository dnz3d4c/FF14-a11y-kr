using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;

namespace FF14Accessibility;

/// <summary>Language for all screen-reader output of the mod.</summary>
public enum LanguageMode
{
    /// <summary>Follow the Windows UI culture, falling back to English.</summary>
    Auto = 0,
    German = 1,
    English = 2,
    Korean = 3,
}

/// <summary>
/// Central language state for every screen-reader announcement the mod makes.
/// Set once at startup from the config and updated by "/acc lang". "Auto"
/// follows the Windows UI culture so users get their OS language with no setup.
///
/// All user-facing strings resolve through <see cref="Services.AccessibilityStrings"/>.
/// Game-provided content (item/NPC names, quest text) is NOT routed through this -
/// it already comes from the game in the player's game language and is spoken
/// verbatim.
///
/// Adding a language is meant to be cheap: one enum member, one row in
/// <see cref="ByCulture"/>, one row in <see cref="Aliases"/>. Nothing else in
/// here has to know how many languages exist.
/// </summary>
public static class Loc
{
    /// <summary>What the user picked. May be <see cref="LanguageMode.Auto"/>.</summary>
    public static LanguageMode Mode { get; set; } = LanguageMode.Auto;

    /// <summary>Language used when the OS culture matches no known one.</summary>
    public const LanguageMode Fallback = LanguageMode.English;

    /// <summary>Two-letter OS culture to language. One row per supported language.</summary>
    private static readonly Dictionary<string, LanguageMode> ByCulture =
        new(StringComparer.OrdinalIgnoreCase)
        {
            ["de"] = LanguageMode.German,
            ["en"] = LanguageMode.English,
            ["ko"] = LanguageMode.Korean,
        };

    /// <summary>What "/acc lang" accepts. Several spellings may map to one language.</summary>
    private static readonly Dictionary<string, LanguageMode> Aliases =
        new(StringComparer.OrdinalIgnoreCase)
        {
            ["de"] = LanguageMode.German,
            ["deutsch"] = LanguageMode.German,
            ["german"] = LanguageMode.German,
            ["en"] = LanguageMode.English,
            ["english"] = LanguageMode.English,
            ["englisch"] = LanguageMode.English,
            ["ko"] = LanguageMode.Korean,
            ["korean"] = LanguageMode.Korean,
            ["koreanisch"] = LanguageMode.Korean,
            ["한국어"] = LanguageMode.Korean,
            ["auto"] = LanguageMode.Auto,
        };

    /// <summary>
    /// The language actually in use. Never <see cref="LanguageMode.Auto"/> -
    /// "Auto" is resolved against the OS culture here, so callers never have to.
    /// </summary>
    public static LanguageMode Current
    {
        get
        {
            if (Mode != LanguageMode.Auto) return Mode;
            var culture = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName;
            return ByCulture.TryGetValue(culture, out var found) ? found : Fallback;
        }
    }

    /// <summary>True when announcements should be German.</summary>
    public static bool IsGerman => Current == LanguageMode.German;

    /// <summary>True when announcements should be Korean.</summary>
    public static bool IsKorean => Current == LanguageMode.Korean;

    /// <summary>
    /// Zweibuchstabiger Sprachcode der laufenden Sprache, fuer fremde APIs, die
    /// nach Kultur auswaehlen statt nach unserem Enum - SAPI zum Beispiel.
    ///
    /// WARUM HIER UND NICHT BEIM AUFRUFER: ein "IsGerman ? de : en" beim Aufrufer
    /// ist genau so lange richtig, wie es zwei Sprachen gibt. Mit der dritten wird
    /// daraus stillschweigend "alles ausser Deutsch ist Englisch" - und still ist
    /// das Schlimme daran, weil eine englische Stimme koreanischen Text ja
    /// vorliest, nur unverstaendlich. Steht die Zuordnung hier, wandert jede
    /// weitere Sprache an einer Stelle mit.
    /// </summary>
    public static string CultureCode => Current switch
    {
        LanguageMode.Korean => "ko",
        LanguageMode.German => "de",
        _ => "en",
    };

    private static Action<string>? _missingKorean;

    /// <summary>
    /// Where a line that has no Korean yet is reported. The plugin hooks its own
    /// log up at startup and clears the hook on dispose; while this is null nothing
    /// is recorded at all.
    ///
    /// WHY A HOOK AND NOT A DIRECT CALL: <see cref="Pick"/> is static and the log
    /// service is injected into the plugin instance, so Pick cannot reach it.
    ///
    /// Setting it also empties <see cref="Reported"/>. A new hook means a new log,
    /// and what the old one already heard is not in it - keeping the old filter
    /// would leave the new log silent about lines that are still untranslated.
    /// </summary>
    public static Action<string>? MissingKorean
    {
        get => _missingKorean;
        set
        {
            _missingKorean = value;
            Reported.Clear();
        }
    }

    /// <summary>
    /// Lines already reported, as (caller, English). Pick runs every frame from
    /// several threads, so without this the log would fill with the same line
    /// thousands of times over. Concurrent because the callers are not on one thread.
    ///
    /// The English text is part of the key, not just the caller name: one property
    /// can hold several sentences (<c>GaugeAttunementType</c> holds four), and on
    /// the caller name alone only the first of them would ever be reported.
    /// </summary>
    private static readonly ConcurrentDictionary<(string Caller, string English), byte>
        Reported = new();

    /// <summary>
    /// Picks the wording for the language in use.
    ///
    /// Korean falls back to English while <paramref name="ko"/> is null. That is
    /// the point: the Korean strings arrive one feature group at a time, and
    /// until a line is translated it has to keep saying something usable rather
    /// than nothing. A blind user cannot tell "not translated yet" from "broken"
    /// if the mod simply goes quiet. The fallback is silent to the ear, so it is
    /// written to the log instead - see <see cref="MissingKorean"/>.
    ///
    /// <paramref name="caller"/> is the FOURTH parameter on purpose. The calls the
    /// assembler writes carry three arguments, so a positional argument can never
    /// land on it and shadow the name the wrapper fills in.
    /// </summary>
    public static string Pick(string de, string en, string? ko = null, string caller = "") =>
        Current switch
        {
            LanguageMode.Korean => ko ?? ReportMissing(caller, en),
            LanguageMode.German => de,
            _ => en,
        };

    /// <summary>Notes one untranslated line and returns the English fallback.</summary>
    private static string ReportMissing(string caller, string en)
    {
        var report = MissingKorean;
        // Nothing is recorded while no one listens: a call from before the plugin
        // hooks this up must not silence that line for the rest of the session.
        if (report is null) return en;

        // The caller name is empty for direct Loc.Pick calls, which have no
        // [CallerMemberName] wrapper. Those are named by their English text alone.
        if (Reported.TryAdd((caller, en), 0))
            report(caller.Length > 0 ? $"{caller}: {en}" : en);
        return en;
    }

    /// <summary>Parses a "/acc lang" argument to a mode, or null if unknown.</summary>
    public static LanguageMode? ParseArg(string arg) =>
        Aliases.TryGetValue(arg.Trim(), out var found) ? found : null;
}
