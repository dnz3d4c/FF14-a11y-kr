namespace FF14AccessibilityInstaller;

/// <summary>
/// Starts the Korean client and the Korean Dalamud updater together, then
/// exits. The whole program is the two lines in <see cref="Main"/>.
///
/// It exists because a shortcut cannot do it. A .lnk points at one target, and
/// pointing one at cmd.exe flashes a console window that steals the foreground
/// from the game that is coming up behind it - the opposite of what somebody
/// using a screen reader needs at that moment.
///
/// Order does not matter to the result. The updater watches for the game
/// process on a one-second tick and attaches to it whenever it appears, so a
/// game that started first is still found. The updater goes first anyway,
/// because it spends a moment checking for its own update before it starts
/// watching.
///
/// Nothing is left running. This process starts two others and ends; there is
/// no tray icon and nothing registered to run at logon.
/// </summary>
internal static class Play
{
    [STAThread]
    private static int Main()
    {
        // The language the installer saved. Nothing to ask here - by the time
        // this shortcut exists the installer has already run once.
        Loc.Current = Loc.LoadSavedLanguage() ?? Loc.Korean;

        var problems = new List<string>();

        // Already open means the user opened it, and a second one would put two
        // injectors on the same game.
        if (!KrProfile.UpdaterRunning() && !KrProfile.TryLaunchUpdater())
            problems.Add(Loc.Get("PlayNoUpdater", KrProfile.UpdaterPath));

        if (!KrProfile.TryLaunchGame())
            problems.Add(Loc.Get("PlayNoGame", KrProfile.GameShortcutPath));

        if (problems.Count == 0) return 0;

        // Said out loud, not swallowed. A launcher that fails quietly is
        // indistinguishable from a game that is slow to start, and the person
        // waiting for it cannot look at the screen to tell the difference.
        MessageBox.Show(
            string.Join(Environment.NewLine + Environment.NewLine, problems),
            Loc.Get("PlayWindowTitle"),
            MessageBoxButtons.OK,
            MessageBoxIcon.Warning);
        return 1;
    }
}
