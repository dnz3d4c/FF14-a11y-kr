using System.IO.Compression;
using System.Security.Cryptography;

namespace FF14AccessibilityInstaller;

/// <summary>
/// Puts the Korean-server Dalamud we publish into the profile, for the window in
/// which the KR updater cannot fetch Dalamud at all.
///
/// **Temporary.** The updater normally downloads official Dalamud and patches it
/// in place, and that is the path we want back. It stalls whenever official
/// Dalamud ships a FFXIVClientStructs the updater was not built against - first
/// measured 2026-09-09, 7.55.1.9047 against the 7.55.1.9032 it carries - and it
/// exposes no way to pick a version, so nobody can work around it from outside.
///
/// **Two ways to switch it off, and the cheap one needs no release.** Failing to
/// fetch returns false and the caller falls straight through to the updater path,
/// so unpublishing the bundle release turns this off for everyone already holding
/// this build. Removing it for good is the file plus the two graft rules named in
/// docs/decisions.md D-13.
///
/// **This does not replace the updater.** That program also injects Dalamud into
/// the running game, and nothing here stands in for that. Whoever ends up on this
/// path still needs it installed, which is why the caller fetches it first.
///
/// Nothing is asked here. Dalamud is not optional the way vnavmesh and the dungeon
/// paths are, and the person already pressed Install; a second yes/no in the middle
/// of a run buys nothing and costs a step to somebody working by ear.
/// </summary>
internal static class KrDalamudBundle
{
    /// <summary>The release page a person can open, printed when fetching fails.</summary>
    public const string ReleasePage =
        "https://github.com/dnz3d4c/FF14-a11y-kr/releases/tag/dalamud-kr-full-15.0.3.3";

    private const string DownloadUrl =
        "https://github.com/dnz3d4c/FF14-a11y-kr/releases/download/dalamud-kr-full-15.0.3.3/dalamud-kr-15.0.3.3-full.zip";

    /// <summary>
    /// SHA-256 of the asset, upper case hex. Checked before anything is unpacked,
    /// because this archive goes straight into the folder Dalamud is loaded from:
    /// a truncated download has to fail loudly rather than half-fill that folder
    /// and leave the game starting against pieces from two different builds.
    /// </summary>
    private const string ArchiveSha256 =
        "EDB86F50E2E1E5FB50A45A2452091970C978E4081CA5A19577BFB14A9DC59C21";

    /// <summary>
    /// Fetches the bundle and puts it into the profile. True only when the profile
    /// afterwards holds everything the rest of the installer looks for; every
    /// failure returns false so the caller can carry on with the updater.
    ///
    /// Everything it needs from the service is passed in rather than reached for,
    /// so this file has no other tie to the installer and deleting it takes the
    /// whole feature with it.
    /// </summary>
    public static async Task<bool> TryInstallAsync(
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

        // The same test the rest of the installer uses, so "we unpacked it" and
        // "the installer sees Dalamud" cannot drift apart. Naming the missing
        // piece is the point: without it a failure here is another silent wait.
        if (KrProfile.DalamudMissingPiece() is { } missing)
        {
            warn(Loc.Get("KrBundleStillMissing", missing));
            return false;
        }

        info(Loc.Get("KrBundleInstalled"));
        return true;
    }

    private static string Sha256Of(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream));
    }
}
