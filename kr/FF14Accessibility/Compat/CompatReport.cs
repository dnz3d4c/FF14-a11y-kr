using System.Collections.Generic;
using Dalamud.Plugin.Services;

namespace FF14Accessibility;

/// <summary>Where an answer the game normally gives comes from now.</summary>
internal enum CompatSource
{
    /// <summary>The game's own function, resolved by ClientStructs.</summary>
    GameFunction,

    /// <summary>The game's own function, found by a Korean-only signature after
    /// ClientStructs failed. Same answer, different way of locating it.</summary>
    KoreanSignature,

    /// <summary>Rebuilt inside the mod. The answer can differ from the game's.</summary>
    Emulated,
}

/// <summary>
/// One place that says out loud which compatibility paths are live.
///
/// The mod is used by people who cannot see the screen, so a fallback that
/// quietly changes an answer is worse than one that fails loudly: there is no
/// way to notice it from the outside. Every path therefore reports itself.
///
/// - the log always gets a line per path, including "the game answers this one"
/// - speech gets ONE line at startup, and only for paths whose answer can
///   differ from the game's. A Korean signature that found the game's own
///   function changes nothing for the user, so it stays in the log.
///
/// Strings live here rather than in AccessibilityStrings because this file is
/// Korean-overlay only. Upstream rewrites that file constantly and every line we
/// add there is a merge conflict later.
/// </summary>
internal static class CompatReport
{
    /// <summary>Runs the probes. Call before the first service is built - the
    /// node visibility path has to be in place before anything reads a node.</summary>
    internal static void Install(ISigScanner scanner, IPluginLog log)
    {
        NodeVisibilityCompat.Install(scanner, log);
        GearsetMarkCompat.Probe(log);

        // The probes log their own findings; this is the summary line, and it is
        // written even when nothing was replaced, so the log always answers
        // "was compatibility involved?".
        log.Information($"[Compat] node visibility: {NodeVisibilityCompat.Source} "
                        + $"(0x{NodeVisibilityCompat.Address:X}), gearset mark: "
                        + $"{(GearsetMarkCompat.AnswersByItemId ? "item id" : "game function")}.");
    }

    /// <summary>Hands back everything the probes took over. Call from
    /// Plugin.Dispose - what this undoes would otherwise outlive the plugin.</summary>
    internal static void Uninstall() => NodeVisibilityCompat.Uninstall();

    /// <summary>What to say once at startup, or null when every answer is the
    /// game's own.</summary>
    internal static string? StartupNotice
    {
        get
        {
            var notes = new List<string>();
            if (NodeVisibilityCompat.Source == CompatSource.Emulated)
                notes.Add(Loc.Pick("Sichtbarkeit von Elementen wird nachgebildet.",
                                   "Element visibility is emulated.",
                                   "화면 요소가 보이는지 모드가 대신 계산함."));
            if (GearsetMarkCompat.AnswersByItemId)
                notes.Add(Loc.Pick("Ausrüstungsset-Markierung geht nach Gegenstands-ID.",
                                   "Gearset marks go by item ID.",
                                   "장비세트 표시는 아이템 ID로 판정함."));

            if (notes.Count == 0) return null;
            var prefix = Loc.Pick("Kompatibilitätshinweis: ", "Compatibility note: ", "호환성 안내: ");
            return prefix + string.Join(" ", notes);
        }
    }
}
