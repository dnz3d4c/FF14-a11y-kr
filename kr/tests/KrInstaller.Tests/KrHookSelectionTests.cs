using System.Text.Json.Nodes;
using FF14AccessibilityInstaller;

namespace KrInstaller.Tests;

public sealed class KrHookSelectionTests : IDisposable
{
    private readonly string _hooks = Path.Combine(Path.GetTempPath(), "krhooks_" + Guid.NewGuid());

    public KrHookSelectionTests() => Directory.CreateDirectory(_hooks);

    public void Dispose()
    {
        try { Directory.Delete(_hooks, recursive: true); }
        catch (IOException) { }
    }

    private void MakeHook(string version, bool marker)
    {
        var dir = Path.Combine(_hooks, version);
        Directory.CreateDirectory(dir);
        File.WriteAllText(Path.Combine(dir, "Dalamud.dll"), "");
        if (marker) File.WriteAllText(Path.Combine(dir, "Dalamud.KR.Compatibility.Patch.json"), "{}");
    }

    [Fact]
    public void Required_hook_with_marker_is_ready()
    {
        MakeHook("15.0.3.7", marker: true);

        Assert.True(KrHookSelection.HookReady(_hooks, "15.0.3.7"));
    }

    [Fact]
    public void An_older_hook_does_not_count_for_the_required_version()
    {
        // The case that slipped through before: 15.0.3.5 carries the KR marker,
        // so "some KR Dalamud is there" was true and the bundle was never fetched.
        MakeHook("15.0.3.5", marker: true);

        Assert.False(KrHookSelection.HookReady(_hooks, "15.0.3.7"));
    }

    [Fact]
    public void A_folder_without_the_KR_marker_is_not_ready()
    {
        MakeHook("15.0.3.7", marker: false);

        Assert.False(KrHookSelection.HookReady(_hooks, "15.0.3.7"));
    }

    [Fact]
    public void A_missing_hooks_folder_is_not_ready()
    {
        Assert.False(KrHookSelection.HookReady(Path.Combine(_hooks, "nope"), "15.0.3.7"));
    }

    [Theory]
    [InlineData("15.0.3.5", true)]
    [InlineData("15.0.3.7", false)]
    [InlineData("15.0.3.8", false)]
    [InlineData("", true)]
    [InlineData("not a version", true)]
    public void Only_an_older_or_unreadable_choice_is_moved(string current, bool expected)
    {
        // A newer choice is left alone: once the updater handles 15.0.3.8 the
        // user may have moved there on purpose, and the plugin binds to it too.
        Assert.Equal(expected, KrHookSelection.ShouldPoint(current, "15.0.3.7"));
    }

    [Fact]
    public void Pointing_the_settings_keeps_every_other_field()
    {
        var json = """
            {
              "ProfileRoot": "%APPDATA%\\XIVLauncherKR",
              "HookVersion": "15.0.3.5",
              "AutoStart": true,
              "DelaySeconds": 1
            }
            """;

        var updated = KrHookSelection.WithHookVersion(json, "15.0.3.7");

        Assert.NotNull(updated);
        var node = JsonNode.Parse(updated!)!.AsObject();
        Assert.Equal("15.0.3.7", (string?)node["HookVersion"]);
        Assert.Equal("%APPDATA%\\XIVLauncherKR", (string?)node["ProfileRoot"]);
        Assert.True((bool)node["AutoStart"]!);
        Assert.Equal(1, (int)node["DelaySeconds"]!);
    }

    [Fact]
    public void Settings_that_are_not_a_json_object_are_left_alone()
    {
        Assert.Null(KrHookSelection.WithHookVersion("not json", "15.0.3.7"));
        Assert.Null(KrHookSelection.WithHookVersion("[1, 2]", "15.0.3.7"));
    }

    [Fact]
    public void The_current_choice_is_read_out_of_the_settings()
    {
        Assert.Equal("15.0.3.5", KrHookSelection.HookVersionIn("""{"HookVersion": "15.0.3.5"}"""));
        Assert.Equal("", KrHookSelection.HookVersionIn("""{"AutoStart": true}"""));
        Assert.Equal("", KrHookSelection.HookVersionIn("broken"));
    }
}
