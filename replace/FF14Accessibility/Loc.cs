using System;
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

    /// <summary>
    /// Picks the wording for the language in use.
    ///
    /// Korean falls back to English while <paramref name="ko"/> is null. That is
    /// the point: the Korean strings arrive one feature group at a time, and
    /// until a line is translated it has to keep saying something usable rather
    /// than nothing. A blind user cannot tell "not translated yet" from "broken"
    /// if the mod simply goes quiet.
    /// </summary>
    public static string Pick(string de, string en, string? ko = null) => Current switch
    {
        LanguageMode.Korean => ko ?? en,
        LanguageMode.German => de,
        _ => en,
    };

    /// <summary>Parses a "/acc lang" argument to a mode, or null if unknown.</summary>
    public static LanguageMode? ParseArg(string arg) =>
        Aliases.TryGetValue(arg.Trim(), out var found) ? found : null;
}
