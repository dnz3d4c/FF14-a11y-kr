using System.IO.Compression;
using System.Security.Cryptography;

namespace FF14AccessibilityInstaller;

/// <summary>
/// Puts the Korean-server Dalamud we publish into the profile, for the window in
/// which the KR updater cannot fetch the version this plugin needs.
///
/// **Temporary.** The updater normally downloads official Dalamud and patches it
/// in place, and that is the path we want back. It stalls whenever official
/// Dalamud ships a FFXIVClientStructs the updater was not built against - measured
/// again 2026-10-18: official 15.0.3.8 against the 15.0.3.7 build that updater
/// 0.5.5 knows - and it exposes no way to pick a version.
///
/// **Two differences from the first version of this file (2026-09).** It used to
/// run only when no KR Dalamud was there at all. A profile still on 15.0.3.5
/// carries the KR marker too, so it looked installed and never got the bundle.
/// And the updater injects whatever its settings name, so a folder for the right
/// version on disk is not enough - the setting has to point at it. Both checks
/// live in <see cref="KrHookSelection"/> and are tested there.
///
/// **Switching it off needs no release.** Failing to fetch carries on with the
/// updater path, so unpublishing the bundle release turns this off for everyone.
/// Removing it for good is this file, KrHookSelection.cs, the graft rule
/// installer-kr-bundle-offer and the KrBundle* strings (docs/decisions.md D-21).
///
/// **This does not replace the updater.** That program also injects Dalamud into
/// the running game, and nothing here stands in for that.
/// </summary>
internal static class KrDalamudBundle
{
    /// <summary>The Dalamud version this plugin is built and checked against.</summary>
    public const string RequiredVersion = "15.0.3.7";

    /// <summary>The release page a person can open, printed when fetching fails.</summary>
    public const string ReleasePage =
        "https://github.com/dnz3d4c/FF14-a11y-kr/releases/tag/dalamud-kr-full-15.0.3.7";

    private const string DownloadUrl =
        "https://github.com/dnz3d4c/FF14-a11y-kr/releases/download/dalamud-kr-full-15.0.3.7/dalamud-kr-15.0.3.7-full.zip";

    /// <summary>
    /// SHA-256 of the asset, upper case hex. Checked before anything is unpacked,
    /// because this archive goes straight into the folder Dalamud is loaded from:
    /// a truncated download has to fail loudly rather than half-fill that folder.
    /// </summary>
    private const string ArchiveSha256 =
        "3806B1D3DFA1ED3FA1069643B7FF44B25E73259483775D6177F00B7BE97FDF8F";

    private static string HooksRoot => Path.Combine(KrProfile.Root, "addon", "Hooks");

    /// <summary>
    /// Makes sure the required version is on disk and the updater is set to it.
    /// Every failure is reported and returns; the caller carries on with the
    /// updater path either way, so nothing here can leave the install worse off.
    ///
    /// Nothing is asked. Dalamud is not optional the way vnavmesh is, and the
    /// person already pressed Install.
    /// </summary>
    public static async Task EnsureAsync(
        Func<string, string, string, Task> download,
        Action<string> info,
        Action<string> warn)
    {
        if (!KrHookSelection.HookReady(HooksRoot, RequiredVersion)
            && !await TryInstallAsync(download, info, warn))
            return;

        PointUpdater(info, warn);
    }

    private static async Task<bool> TryInstallAsync(
        Func<string, string, string, Task> download,
        Action<string> info,
        Action<string> warn)
    {
        var archivePath = Path.Combine(
            Path.GetTempPath(), "kr_dalamud_bundle_" + Guid.NewGuid() + ".zip");
        try
        {
            info(Loc.Get("KrBundleDownloading"));
            await download(DownloadUrl, archivePath, Loc.Get("KrBundleDownloadLabel"));

            if (!string.Equals(Sha256Of(archivePath), ArchiveSha256, StringComparison.OrdinalIgnoreCase))
            {
                warn(Loc.Get("KrBundleHashMismatch"));
                info(Loc.Get("KrBundleGetByHand"));
                info("  " + ReleasePage);
                return false;
            }

            info(Loc.Get("KrBundleInstalling"));
            Directory.CreateDirectory(KrProfile.Root);
            ZipFile.ExtractToDirectory(archivePath, KrProfile.Root, overwriteFiles: true);
        }
        catch (Exception ex)
        {
            warn(Loc.Get("KrBundleFailed", ex.Message));
            info(Loc.Get("KrBundleGetByHand"));
            info("  " + ReleasePage);
            return false;
        }
        finally
        {
            // Losing the temp file matters less than stopping here would.
            try { File.Delete(archivePath); }
            catch (Exception) { }
        }

        // The same tests the rest of the installer uses, so "we unpacked it" and
        // "the installer sees Dalamud" cannot drift apart.
        if (!KrHookSelection.HookReady(HooksRoot, RequiredVersion))
        {
            warn(Loc.Get("KrBundleStillMissing", Path.Combine(HooksRoot, RequiredVersion)));
            return false;
        }
        if (KrProfile.DalamudMissingPiece() is { } missing)
        {
            warn(Loc.Get("KrBundleStillMissing", missing));
            return false;
        }

        info(Loc.Get("KrBundleInstalled"));
        return true;
    }

    /// <summary>
    /// Sets the updater to inject the required version. Without this a profile
    /// that was on 15.0.3.5 gets the new folder and keeps starting the old one -
    /// measured on the development machine on 2026-10-18.
    ///
    /// No settings file means a first install: the updater writes its own on first
    /// start, and updater 0.5.5 defaults to 15.0.3.7. Nothing to do then.
    /// </summary>
    private static void PointUpdater(Action<string> info, Action<string> warn)
    {
        var path = KrProfile.UpdaterSettingsPath;
        if (!File.Exists(path)) return;

        try
        {
            var text = File.ReadAllText(path);
            var current = KrHookSelection.HookVersionIn(text);
            if (!KrHookSelection.ShouldPoint(current, RequiredVersion)) return;

            if (KrHookSelection.WithHookVersion(text, RequiredVersion) is not { } updated)
            {
                warn(Loc.Get("KrHookVersionByHand", RequiredVersion));
                return;
            }
            // The one write into another program's settings (KrProfile.Root has the
            // rule and this exception). The backup is what lets it be undone by hand.
            File.Copy(path, path + ".bak-installer", overwrite: true);
            File.WriteAllText(path, updated);
            info(Loc.Get("KrHookVersionSet", RequiredVersion));
        }
        catch (Exception ex)
        {
            warn(Loc.Get("KrBundleFailed", ex.Message));
            warn(Loc.Get("KrHookVersionByHand", RequiredVersion));
        }
    }

    private static string Sha256Of(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream));
    }
}
