using System.Text.Json;
using System.Text.Json.Nodes;

namespace FF14AccessibilityInstaller;

/// <summary>
/// Which Dalamud hook the Korean setup has to end up on. Kept apart from the
/// installer so it can be tested without WinForms, Loc or the network
/// (tests/KrInstaller.Tests).
///
/// Two separate questions, because getting only one of them right was exactly
/// the failure of 2026-10-18: the hook folder for the required version can be on
/// disk while the KR updater is still set to inject an older one, and then the
/// game starts on a Dalamud the plugin was not built against.
/// </summary>
internal static class KrHookSelection
{
    /// <summary>The KR patch markers the updater writes into a hook folder.</summary>
    public const string KrPatchMarker = "Dalamud.KR.*.Patch.json";

    /// <summary>The key the KR updater keeps its chosen hook version under.</summary>
    public const string HookVersionKey = "HookVersion";

    /// <summary>
    /// True when <paramref name="hooksRoot"/>\<paramref name="version"/> exists and
    /// carries a KR patch marker. Some other version being there does not count -
    /// that was the hole: 15.0.3.5 carries the marker too.
    /// </summary>
    public static bool HookReady(string hooksRoot, string version)
    {
        try
        {
            var dir = Path.Combine(hooksRoot, version);
            return Directory.Exists(dir) && Directory.EnumerateFiles(dir, KrPatchMarker).Any();
        }
        catch (Exception)
        {
            // The updater may be writing into the same tree. Not being able to
            // look right now is "not ready", the same as KrProfile treats it.
            return false;
        }
    }

    /// <summary>
    /// Whether the updater's choice should be moved to <paramref name="required"/>.
    /// Only an older or unreadable choice is moved. A newer one is left alone: the
    /// user may have moved there on purpose once the updater handles it.
    /// </summary>
    public static bool ShouldPoint(string current, string required)
    {
        if (!Version.TryParse(required, out var want)) return false;
        if (!Version.TryParse(current, out var have)) return true;
        return have < want;
    }

    /// <summary>The updater's chosen hook version, or "" when there is none to read.</summary>
    public static string HookVersionIn(string settingsJson)
    {
        try
        {
            return JsonNode.Parse(settingsJson) is JsonObject settings
                   && settings[HookVersionKey] is JsonValue value
                   && value.TryGetValue<string>(out var text)
                ? text
                : "";
        }
        catch (JsonException)
        {
            return "";
        }
    }

    /// <summary>
    /// The settings text with only the hook version changed, or null when it is not
    /// a JSON object. Null means "do not write": rewriting a file we cannot read
    /// would throw away whatever the updater keeps in it.
    /// </summary>
    public static string? WithHookVersion(string settingsJson, string version)
    {
        try
        {
            if (JsonNode.Parse(settingsJson) is not JsonObject settings) return null;
            settings[HookVersionKey] = version;
            return settings.ToJsonString(new JsonSerializerOptions { WriteIndented = true });
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
