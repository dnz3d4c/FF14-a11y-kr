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
/// Removing it for good is described in docs/decisions.md D-21.
///
/// **This does not replace the updater.** That program also injects Dalamud into
/// the running game, and nothing here stands in for that.
/// </summary>
internal static class KrDalamudBundle
{
    /// <summary>The Dalamud version this plugin is built and checked against.</summary>
    public const string RequiredVersion = "15.0.3.7";

    /// <summary>The asset package the bundle carries, and the oldest one accepted.</summary>
    public const int RequiredAssets = 445;

    /// <summary>The release page a person can open, printed when fetching fails.</summary>
    public const string ReleasePage =
        "https://github.com/dnz3d4c/FF14-a11y-kr/releases/tag/dalamud-kr-full-15.0.3.7";

    private const string DownloadUrl =
        "https://github.com/dnz3d4c/FF14-a11y-kr/releases/download/dalamud-kr-full-15.0.3.7/dalamud-kr-15.0.3.7-full.zip";

    /// <summary>
    /// SHA-256 of the asset, upper case hex. Checked before anything is unpacked,
    /// because this archive goes straight into the folder Dalamud is loaded from.
    /// </summary>
    private const string ArchiveSha256 =
        "3806B1D3DFA1ED3FA1069643B7FF44B25E73259483775D6177F00B7BE97FDF8F";

    private static string HooksRoot => Path.Combine(KrProfile.Root, "addon", "Hooks");
    private static string AssetsRoot => Path.Combine(KrProfile.Root, "dalamudAssets");

    /// <summary>
    /// Makes sure the required hook and assets are on disk and the updater is set
    /// to that hook. Every failure is reported and returns; the caller carries on
    /// with the updater path either way.
    ///
    /// Nothing is asked. Dalamud is not optional the way vnavmesh is, and the
    /// person already pressed Install.
    /// </summary>
    public static async Task EnsureAsync(
        Func<string, string, string, Task> download,
        Action<string> info,
        Action<string> warn)
    {
        var complete = KrHookSelection.HookReady(HooksRoot, RequiredVersion)
                       && KrHookSelection.AssetsReady(KrProfile.AssetVersionPath, RequiredAssets);
        if (!complete && !await TryInstallAsync(download, info, warn))
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
        // Unpacked next to the profile, not into it, so a run that dies half way -
        // full disk, a locked file - leaves the profile as it was. Same volume as
        // the targets, so the moves below are renames, not copies.
        var staging = Path.Combine(KrProfile.Root, ".kr-bundle-staging-" + Guid.NewGuid());
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
            ZipFile.ExtractToDirectory(archivePath, staging);
            Place(staging);
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
            // Losing the temp files matters less than stopping here would.
            try { File.Delete(archivePath); }
            catch (Exception) { }
            try { if (Directory.Exists(staging)) Directory.Delete(staging, recursive: true); }
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
    /// Moves the unpacked hook and assets into the profile, and writes asset.ver
    /// last. A hook folder that is already complete stays: it is the same build,
    /// and the running game may hold it open.
    /// </summary>
    private static void Place(string staging)
    {
        var stagedHook = Path.Combine(staging, "addon", "Hooks", RequiredVersion);
        var stagedAssets = Path.Combine(staging, "dalamudAssets", RequiredAssets.ToString());
        if (!KrHookSelection.HookReady(Path.Combine(staging, "addon", "Hooks"), RequiredVersion)
            || !Directory.Exists(stagedAssets))
            throw new InvalidDataException(Loc.Get("KrBundleStillMissing", staging));

        if (!KrHookSelection.HookReady(HooksRoot, RequiredVersion))
            Replace(stagedHook, Path.Combine(HooksRoot, RequiredVersion));
        Replace(stagedAssets, Path.Combine(AssetsRoot, RequiredAssets.ToString()));

        Directory.CreateDirectory(Path.Combine(AssetsRoot, "local"));
        var verTemp = KrProfile.AssetVersionPath + ".kr-bundle-tmp";
        File.WriteAllText(verTemp, RequiredAssets.ToString());
        File.Move(verTemp, KrProfile.AssetVersionPath, overwrite: true);
    }

    /// <summary>
    /// Puts <paramref name="from"/> where <paramref name="to"/> is. Whatever was at
    /// the target is a half-written folder from an earlier run, or the same
    /// package number: neither is worth keeping over a verified copy.
    /// </summary>
    private static void Replace(string from, string to)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(to)!);
        if (Directory.Exists(to)) Directory.Delete(to, recursive: true);
        Directory.Move(from, to);
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

        var temp = path + ".kr-bundle-tmp";
        try
        {
            var text = File.ReadAllText(path);
            if (!KrHookSelection.ShouldPoint(KrHookSelection.HookVersionIn(text), RequiredVersion))
                return;

            if (KrHookSelection.WithHookVersion(text, RequiredVersion) is not { } updated)
            {
                warn(Loc.Get("KrHookVersionByHand", RequiredVersion));
                return;
            }

            // The one write into another program's settings (KrProfile.Root has the
            // rule and this exception). File.Replace swaps the file and keeps the old
            // one as the backup in one step, so a failed write cannot leave the
            // updater with a truncated settings file.
            File.WriteAllText(temp, updated);
            File.Replace(temp, path, path + ".bak-installer");
            info(Loc.Get("KrHookVersionSet", RequiredVersion));
        }
        catch (Exception ex)
        {
            warn(Loc.Get("KrBundleFailed", ex.Message));
            warn(Loc.Get("KrHookVersionByHand", RequiredVersion));
        }
        finally
        {
            try { File.Delete(temp); }
            catch (Exception) { }
        }
    }

    private static string Sha256Of(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream));
    }
}
