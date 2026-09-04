using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;

namespace FF14AccessibilityInstaller;

/// <summary>
/// Minimal static localization helper (DE/EN). No resx needed - just two
/// dictionaries and a Get(key) lookup. Keeps the current UI language in
/// <see cref="Current"/> and persists the user's choice to
/// %APPDATA%\FF14AccessibilityInstaller\installer-settings.json so it can be
/// pre-selected (not auto-applied) the next time the language dialog shows.
/// </summary>
public static class Loc
{
    public const string German = "de";
    public const string English = "en";
    public const string Korean = "ko";

    /// <summary>Currently active UI language. The Korean build defaults to Korean.</summary>
    public static string Current { get; set; } = Korean;

    public static string Get(string key)
    {
        if (Texts.TryGetValue(Current, out var dict) && dict.TryGetValue(key, out var value))
            return value;
        // Fallback auf Englisch, nicht Deutsch: was hier durchfaellt, liest sonst
        // ein koreanischer Nutzer als deutschen Satz vor.
        if (Texts[English].TryGetValue(key, out var fallback))
            return fallback;
        return key;
    }

    public static string Get(string key, params object?[] args) => string.Format(Get(key), args);

    // ── Sprache erkennen/merken ─────────────────────────────────────────────

    private static readonly string SettingsDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "FF14AccessibilityInstaller");
    private static readonly string SettingsPath = Path.Combine(SettingsDir, "installer-settings.json");

    /// <summary>Reads the previously saved language, or null if none was saved yet.</summary>
    public static string? LoadSavedLanguage()
    {
        try
        {
            if (!File.Exists(SettingsPath)) return null;
            var json = File.ReadAllText(SettingsPath);
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("language", out var langProp))
            {
                var lang = langProp.GetString();
                if (lang == German || lang == English || lang == Korean) return lang;
            }
        }
        catch
        {
            // Beschädigte/fehlende Settings-Datei ist kein Fehlerfall - einfach neu fragen.
        }
        return null;
    }

    public static void SaveLanguage(string language)
    {
        try
        {
            Directory.CreateDirectory(SettingsDir);
            var json = JsonSerializer.Serialize(new { language });
            File.WriteAllText(SettingsPath, json);
        }
        catch
        {
            // Nicht kritisch - beim naechsten Start wird einfach wieder gefragt.
        }
    }

    /// <summary>
    /// Detects whether the system UI language is German, via a raw Win32 call
    /// (GetUserDefaultLocaleName) rather than CultureInfo. The project sets
    /// InvariantGlobalization=true (see csproj), which makes .NET's own
    /// CultureInfo.CurrentUICulture always report the invariant culture - so
    /// we bypass that and ask Windows directly.
    /// </summary>
    public static bool SystemLanguageIsGerman()
    {
        try
        {
            var sb = new StringBuilder(85);
            if (GetUserDefaultLocaleName(sb, sb.Capacity) > 0)
                return sb.ToString().StartsWith("de", StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            // Falls der Aufruf scheitert, bleibt es bei Englisch als Fallback.
        }
        return false;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetUserDefaultLocaleName(StringBuilder lpLocaleName, int cchLocaleName);

    // ── Texte ────────────────────────────────────────────────────────────────

    private static readonly Dictionary<string, Dictionary<string, string>> Texts = new()
    {
        [German] = new Dictionary<string, string>
        {
            ["WarnPrefix"] = "Achtung: ",
            ["ErrorPrefix"] = "Fehler: ",
            ["UnknownVersion"] = "unbekannt",

            ["InstallerHeader"] = "FF14 Accessibility – Installer und Updater (Version {0}).",
            ["CheckingXivLauncher"] = "Prüfe XIVLauncher ...",
            ["XivLauncherFound"] = "XIVLauncher gefunden.",
            ["SummaryHeader"] = "=== Zusammenfassung ===",
            ["SummaryAccessibility"] = "FF14 Accessibility: {0}",
            ["SummaryVnavmesh"] = "vnavmesh (Auto-Lauf): {0}",
            ["SummaryDungeonPaths"] = "Dungeon-Wege: {0}",

            // Wegdateien für die Kategorie "Dungeon"
            ["CheckingDungeonPaths"] = "Lade die Wegdateien für die Kategorie „Dungeon\" ...",
            ["DungeonPathsWritten"] = "{0} Wegdateien geschrieben nach {1}",
            ["DungeonPathsSummary"] = "{0} Wege geladen",
            ["DungeonPathsUnreachable"] = "Die Wegdateien sind gerade nicht erreichbar ({0}). Das Plugin holt sie beim ersten Start selbst nach.",
            ["DungeonPathsTimeout"] = "Zeitüberschreitung beim Laden der Wegdateien. Das Plugin holt sie beim ersten Start selbst nach.",
            ["DungeonPathsNothingInArchive"] = "Im geladenen Archiv steckt keine einzige Wegdatei - die Quelle hat ihren Aufbau geändert.",
            ["DungeonPathsArchiveTooBig"] = "Das Archiv ist unerwartet groß und wurde nicht entpackt.",
            ["DungeonPathsUnexpectedError"] = "Die Wegdateien konnten nicht geschrieben werden: {0}",
            ["UnexpectedError"] = "Unerwarteter Fehler: {0}",
            ["NoPartialWrite"] = "Es wurde nichts Unvollständiges geschrieben, das dein System beschädigt.",
            ["UnexpectedErrorWhere"] = "Wie weit es gekommen ist, steht in den Statusmeldungen darueber.",

            ["XivLauncherNotInstalled1"] = "XIVLauncher ist nicht installiert (Ordner nicht gefunden:",
            ["XivLauncherNotInstalled2"] = "  {0}).",
            ["XivLauncherNeeded"] = "XIVLauncher wird gebraucht, weil es Dalamud lädt – die Grundlage für das Plugin.",
            ["DownloadingXivLauncherAuto"] = "Lade die neueste XIVLauncher-Version herunter und installiere sie automatisch ...",
            ["GitHubUnreachable"] = "GitHub nicht erreichbar ({0}). Bitte Internetverbindung prüfen.",
            ["InstallXivLauncherManually1"] = "Installiere XIVLauncher alternativ manuell von https://goatcorp.github.io/ und",
            ["RunProgramAgain"] = "führe dieses Programm danach erneut aus.",
            ["TimeoutFetchXivLauncher"] = "Zeitüberschreitung beim Abruf der XIVLauncher-Version. Bitte Internetverbindung prüfen.",
            ["NoXivLauncherSetupFound"] = "Kein XIVLauncher-Setup im neuesten Release gefunden.",
            ["InstallXivLauncherManually2"] = "Bitte installiere XIVLauncher manuell von https://goatcorp.github.io/ .",
            ["DownloadingXivLauncherVersion"] = "Lade XIVLauncher {0} herunter ({1}) ...",
            ["DownloadFailedInstallManually"] = "Download fehlgeschlagen ({0}). Bitte installiere XIVLauncher manuell von",
            ["UrlAndRunAgain"] = "https://goatcorp.github.io/ und führe dieses Programm danach erneut aus.",
            ["TimeoutDownloadRetry"] = "Zeitüberschreitung beim Download. Bitte Internetverbindung prüfen und erneut versuchen.",
            ["XivLauncherSaveFailed"] = "XIVLauncher-Setup konnte nicht gespeichert werden: {0}",
            ["InstallingXivLauncherSilent"] = "Installiere XIVLauncher automatisch im Hintergrund (--silent) ...",
            ["XivLauncherInstallStarted"] = "XIVLauncher-Installation wurde gestartet und sollte inzwischen abgeschlossen sein.",
            ["AutoInstallNotConfirmed"] = "Die automatische Installation konnte nicht bestätigt werden ({0}).",
            ["RunSetupManuallyHint"] = "Falls XIVLauncher nicht gestartet ist, führe die Datei manuell aus:",
            ["LoginHint1"] = "Bitte melde dich jetzt im XIVLauncher an, aktiviere in den Einstellungen",
            ["LoginHint2"] = "Dalamud und starte das Spiel EINMAL. Führe diesen Installer danach erneut",
            ["LoginHint3"] = "aus, um das Barrierefreiheits-Plugin einzurichten.",

            // Selbst-Update des Installers
            ["CheckingInstallerVersion"] = "Prüfe, ob es eine neuere Installer-Version gibt ...",
            ["NoInstallerManifest"] = "Keine Installer-Versionsangabe im Release gefunden - überspringe die Prüfung.",
            ["InstallerCheckFailed"] = "Installer-Version konnte nicht geprüft werden ({0}). Der Installer arbeitet normal weiter.",
            ["InstallerManifestUnreadable"] = "Installer-Versionsangabe war nicht lesbar - überspringe die Prüfung.",
            ["InstallerUpToDate"] = "Der Installer ist aktuell (Version {0}).",
            ["InstallerAssetMissing"] = "Die neue Installer-Datei ({0}) fehlt im Release - überspringe das Update.",
            ["InstallerOwnPathUnknown"] = "Eigener Programmpfad nicht ermittelbar - überspringe das Installer-Update.",
            ["InstallerUpdateAvailable"] = "Neue Installer-Version verfügbar: {0} (installiert ist {1}).",
            ["InstallerUpdateQuestion"] =
                "Es gibt eine neuere Version des Installers ({0}).\n\n" +
                "Soll sie jetzt heruntergeladen und gestartet werden? Der Download ist etwa {1} Megabyte groß.\n\n" +
                "Der Installer schließt sich dabei kurz und öffnet sich automatisch neu. " +
                "Danach läuft die Installation von selbst weiter.\n\n" +
                "Ja = jetzt aktualisieren, Nein = mit der aktuellen Version weiterarbeiten.",
            ["InstallerUpdateDeclined"] = "Installer-Update übersprungen. Es geht mit der vorhandenen Version weiter.",
            ["DownloadingInstaller"] = "Lade Installer-Version {0} herunter ...",
            ["InstallerDownloadLabel"] = "Installer",
            ["InstallerDownloadFailed"] = "Installer-Update konnte nicht geladen werden ({0}). Es geht mit der vorhandenen Version weiter.",
            ["InstallerHashOk"] = "Prüfsumme der neuen Installer-Datei stimmt.",
            ["InstallerNoHash"] = "Keine Prüfsumme im Release hinterlegt - Download wird ungeprüft übernommen.",
            ["InstallerHashMismatch"] = "Die Prüfsumme der geladenen Installer-Datei stimmt NICHT. Update abgebrochen, es geht mit der vorhandenen Version weiter.",
            ["InstallerStartFailed"] = "Der neue Installer konnte nicht gestartet werden ({0}). Es geht mit der vorhandenen Version weiter.",
            ["InstallerRestarting"] = "Installer wird auf Version {0} aktualisiert. Das Fenster schließt sich jetzt und öffnet sich gleich automatisch neu ...",
            ["InstallerUpdatedTo"] = "Installer wurde auf Version {0} aktualisiert. Die Installation läuft automatisch weiter.",
            ["InstallerUpdatedMessage"] =
                "Der Installer wurde auf Version {0} aktualisiert und neu gestartet.\n\n" +
                "Die Installation läuft nach dem Bestätigen automatisch weiter - du musst nichts weiter tun.",
            ["SelfUpdateNoOwnPath"] =
                "Der eigene Programmpfad war nicht ermittelbar. Die alte Installer-Datei bleibt bestehen; " +
                "dieses Fenster arbeitet aus dem temporären Ordner weiter.",
            ["SelfUpdateReplaceFailed"] =
                "Die vorhandene Installer-Datei konnte nicht ersetzt werden:\n{0}\n\nGrund: {1}\n\n" +
                "Die Installation kann trotzdem weiterlaufen. Wenn du die neue Version dauerhaft behalten willst, " +
                "lade FF14AccessibilityInstaller.exe einmal von Hand aus dem neuesten Release herunter.",
            ["SelfUpdateRestartFailed"] =
                "Die Installer-Datei wurde aktualisiert, konnte aber nicht automatisch gestartet werden:\n{0}\n\nGrund: {1}\n\n" +
                "Bitte starte sie von Hand.",

            ["CheckingAccessibilityVersion"] = "Prüfe neueste Version von FF14 Accessibility ...",
            ["NoAccessibilityAssetFound"] = "Kein passendes Release-Paket für FF14 Accessibility gefunden.",
            ["ErrorNoReleaseAsset"] = "Fehler (kein Release-Asset gefunden)",
            ["AccessibilityUpToDate"] = "FF14 Accessibility ist aktuell (Version {0}).",
            ["UpToDateShort"] = "aktuell (Version {0})",
            ["DownloadingAccessibility"] = "Lade FF14 Accessibility {0} herunter ...",
            ["AccessibilityUpdated"] = "FF14 Accessibility aktualisiert auf Version {0}.",
            ["AccessibilityInstalled"] = "FF14 Accessibility installiert (Version {0}).",
            ["UpdatedToShort"] = "aktualisiert auf {0}",
            ["NewlyInstalledShort"] = "neu installiert, Version {0}",
            ["CouldNotWritePluginFiles"] = "Konnte Plugin-Dateien nicht schreiben: {0}",
            ["CloseGameAndLauncher"] = "Bitte schließe FINAL FANTASY XIV und den XIVLauncher vollständig und versuche es erneut.",
            ["ErrorFilesLocked"] = "Fehler (Dateien gesperrt – bitte Spiel/Launcher schließen)",
            ["AccessibilityGitHubUnreachable"] = "FF14 Accessibility: GitHub nicht erreichbar ({0}).",
            ["ErrorNoNetworkGitHub"] = "Fehler (kein Netzwerk/GitHub nicht erreichbar)",
            ["AccessibilityDownloadTimeout"] = "FF14 Accessibility: Zeitüberschreitung beim Download.",
            ["ErrorTimeout"] = "Fehler (Zeitüberschreitung)",
            ["AccessibilityUnexpectedError"] = "FF14 Accessibility: Unerwarteter Fehler ({0}).",
            ["ErrorGeneric"] = "Fehler",

            ["CheckingVnavmeshVersion"] = "Prüfe neueste Version von vnavmesh (Auto-Lauf) ...",
            ["VnavmeshPunishUnreachable"] = "vnavmesh: puni.sh nicht erreichbar ({0}). Auto-Lauf bleibt unverändert.",
            ["ErrorNoNetworkPunish"] = "Fehler (kein Netzwerk/puni.sh nicht erreichbar)",
            ["VnavmeshPunishTimeout"] = "vnavmesh: Zeitüberschreitung bei puni.sh.",
            ["VnavmeshNotFound"] = "vnavmesh nicht im puni.sh-Repository gefunden.",
            ["ErrorNotFound"] = "Fehler (nicht gefunden)",
            ["VnavmeshNoDownloadLink"] = "vnavmesh: kein Download-Link im Repository gefunden.",
            ["ErrorNoDownloadLink"] = "Fehler (kein Download-Link)",
            ["VnavmeshUpToDate"] = "vnavmesh ist aktuell (Version {0}).",
            ["AutoWalkNeedsVnav1"] = "Das Auto-Lauf-Feature (automatisch zu Zielen laufen) braucht das separate",
            ["AutoWalkNeedsVnav2"] = "Plugin vnavmesh. Es stammt von einem anderen Autor (veyn) und wird vom",
            ["AutoWalkNeedsVnav3"] = "Original geladen, nicht von uns weitergegeben.",
            ["AskSetupVnavmesh"] = "Soll vnavmesh jetzt für den Auto-Lauf eingerichtet werden?",
            ["VnavmeshSkipped"] = "vnavmesh übersprungen. Alles außer dem Auto-Lauf funktioniert trotzdem.",
            ["SkippedShort"] = "übersprungen",
            ["OkShort"] = "eingerichtet",
            ["ErrorShort"] = "fehlgeschlagen",
            ["SummaryPlayLauncher"] = "Spiel-Verknuepfung: {0}",
            ["PlayLauncherInstalling"] = "Richte die Verknuepfung ein, die Spiel und Updater zusammen startet ...",
            ["PlayLauncherMissingResource"] = "Der Launcher steckt nicht in dieser EXE - der Build hat ihn nicht eingebettet.",
            ["PlayLauncherFailed"] = "Der Launcher liess sich nicht ablegen: {0}",
            ["PlayLauncherShortcutMade"] = "Verknuepfung angelegt: {0}",
            ["PlayLauncherShortcutFailed"] = "Verknuepfung liess sich nicht anlegen: {0}",
            ["PlayLauncherRunItDirectly"] = "Der Launcher selbst liegt hier und laesst sich direkt starten:",
            ["PlayLauncherReady"] = "Ab jetzt startet die Verknuepfung {0} Spiel und Updater zusammen. Danach nur noch einloggen.",
            ["DownloadingVnavmesh"] = "Lade vnavmesh {0} herunter ...",
            ["VnavmeshUpdated"] = "vnavmesh aktualisiert auf Version {0}.",
            ["VnavmeshSetup"] = "vnavmesh eingerichtet (Version {0}).",
            ["NewlySetupShort"] = "neu eingerichtet, Version {0}",
            ["VnavmeshCouldNotWriteFiles"] = "vnavmesh: Konnte Dateien nicht schreiben: {0}",
            ["VnavmeshDownloadFailed"] = "vnavmesh: Download fehlgeschlagen ({0}).",
            ["ErrorNoNetwork"] = "Fehler (kein Netzwerk)",
            ["VnavmeshDownloadTimeout"] = "vnavmesh: Zeitüberschreitung beim Download.",
            ["VnavmeshUnexpectedError"] = "vnavmesh: Unerwarteter Fehler ({0}).",

            ["ConfigNotExist1"] = "dalamudConfig.json existiert noch nicht – Dalamud legt sie erst beim",
            ["ConfigNotExist2"] = "ersten Spielstart an. Starte das Spiel EINMAL über XIVLauncher (mit",
            ["ConfigNotExist3"] = "aktiviertem Dalamud) und führe diesen Installer danach erneut aus, damit",
            ["ConfigNotExist4"] = "die Plugins aktiviert werden können.",
            ["ConfigMissingReturn"] = "dalamudConfig.json fehlt noch – bitte Spiel einmal starten und Installer erneut ausführen.",
            ["ConfigReadFailed"] = "dalamudConfig.json konnte nicht gelesen werden: {0}",
            ["ConfigReadFailedReturn"] = "Fehler beim Lesen von dalamudConfig.json (Datei gesperrt?).",
            ["ConfigParseFailed"] = "dalamudConfig.json ließ sich nicht lesen ({0}).",
            ["ConfigNotTouching"] = "Ich fasse sie nicht an. Bitte melde dich – hier ist Handarbeit sicherer.",
            ["ConfigInvalidReturn"] = "Fehler: dalamudConfig.json ungültig, nicht verändert.",
            ["ConfigUnexpectedStructure"] = "Unerwarteter Aufbau der Konfiguration (DevPluginLoadLocations fehlt).",
            ["ConfigSafetyNoChange1"] = "Zur Sicherheit wird nichts geändert. Bitte starte das Spiel einmal und",
            ["ConfigSafetyNoChange2"] = "versuche es erneut.",
            ["ConfigUnexpectedStructureReturn"] = "Fehler: unerwarteter Aufbau von dalamudConfig.json, nicht verändert.",
            ["ConfigUpdated"] = "Konfiguration aktualisiert (Sicherung: {0}).",
            ["ProfileStructureUnexpected"] = "Unerwarteter Aufbau der Konfiguration (DefaultProfile fehlt) – Plugins konnten nicht aktiviert werden. Bitte melde dich.",
            ["ProfileStructureUnexpectedReturn"] = "Fehler: Plugins eingetragen, aber Aktivierung nicht möglich (DefaultProfile fehlt).",
            ["PluginsRegisteredEnabledReturn"] = "Plugins eingetragen und aktiviert.",
            ["ConfigWriteFailed"] = "dalamudConfig.json konnte nicht geschrieben werden: {0}",
            ["ConfigWriteFailedReturn"] = "Fehler beim Schreiben von dalamudConfig.json (Datei gesperrt?).",

            ["DownloadProgress"] = "{0}: {1} % ...",

            ["PlayShortcutName"] = "FF14 Accessibility spielen",
            ["PlayNoUpdater"] = "Der KR-Dalamud-Updater liess sich nicht starten: {0}. Bitte den Installer noch einmal ausfuehren.",
            ["PlayNoGame"] = "Das Spiel liess sich nicht starten. Die Verknuepfung fehlt: {0}",
            ["WindowTitle"] = "FF14 Accessibility – Installer",
            ["MainTitleWithVersion"] = "FF14 Accessibility – Installer und Updater (Version {0})",
            ["MainTitleAccessibleName"] = "FF14 Accessibility Installer, Version {0}",
            ["LogBoxAccessibleName"] = "Statusmeldungen",
            ["LogBoxAccessibleDescription"] = "Fortschritts- und Ergebnismeldungen des Installers, mit Pfeiltasten durchgehbar.",
            ["InstallButtonText"] = "Installieren / Aktualisieren",
            ["InstallButtonAccessibleName"] = "Installieren oder Aktualisieren",
            ["ExitButtonText"] = "Beenden",
            ["ExitButtonAccessibleName"] = "Beenden",
            ["OperationCompleted"] = "Vorgang abgeschlossen. Details siehe Log-Bereich im Fenster.",

            ["LanguageDialogTitle"] = "Sprache wählen / Choose language",
            ["LanguageGermanButton"] = "Deutsch",
            ["LanguageEnglishButton"] = "English",
            ["KrCheckingProfile"] = "Pruefe das koreanische Profil ...",
            ["KrProfileRoot"] = "Profilordner: {0}  (entschieden durch: {1})",
            ["KrProfileFound"] = "Profil vorhanden.",
            ["KrProfileCreated"] = "Fehlende Teile angelegt: {0}",
            ["KrRuntimeVariableSet"] = "DALAMUD_RUNTIME gesetzt: {0}",
            ["KrRuntimeNeedsRestart"] = "Das Spiel muss danach neu gestartet werden - Prozesse erben die Umgebung beim Start.",
            ["KrRuntimeNoDotnet"] = "Kein .NET gefunden ({0}). DALAMUD_RUNTIME bleibt leer, und ohne die Variable startet Dalamud im Spiel nicht - gemeldet wird das nirgends.",
            ["KrRuntimeGetDotnet"] = "Bitte die .NET-Desktop-Runtime installieren und dieses Programm danach erneut ausfuehren.",
            ["DotnetPresent"] = ".NET {0} Desktop-Runtime ist vorhanden: {1}",
            ["DotnetMissing"] = ".NET {0} Desktop-Runtime fehlt ({1}). Ohne sie startet Dalamud im Spiel nicht.",
            ["AskInstallDotnet"] = "Die .NET {0} Desktop-Runtime jetzt herunterladen und installieren?",
            ["DotnetInstallDeclined"] = "Nicht installiert. Das Spiel startet, das Plugin bleibt stumm.",
            ["DotnetSkipped"] = ".NET-Installation ist per FF14ACC_SKIP_DOTNET abgeschaltet.",
            ["DotnetLabel"] = ".NET Desktop-Runtime",
            ["DotnetDownloading"] = "Lade die .NET Desktop-Runtime herunter ...",
            ["DotnetDownloadFailed"] = "Download der .NET-Runtime fehlgeschlagen: {0}",
            ["DotnetGetByHand"] = "Die Runtime kann von hier von Hand geholt werden:",
            ["DotnetInstalling"] = "Installiere die .NET Desktop-Runtime. Das dauert einen Moment; bitte die Windows-Abfrage bestaetigen.",
            ["DotnetInstalled"] = ".NET {0} Desktop-Runtime installiert.",
            ["DotnetRebootRequired"] = "Windows verlangt einen Neustart, bevor die Runtime benutzt werden kann.",
            ["DotnetInstallCancelled"] = "Die Windows-Abfrage wurde abgebrochen, die Runtime wurde nicht installiert.",
            ["DotnetInstallFailed"] = "Installation der .NET-Runtime fehlgeschlagen (Code {0}).",
            ["KrDalamudMissing"] = "Koreanisches Dalamud ist noch nicht installiert.",
            ["KrDalamudGetIt"] = "Bitte zuerst den KR-Dalamud-Updater ausfuehren und \"Check Update\" druecken:",
            ["KrDalamudThenCheckUpdate"] = "Danach dieses Programm erneut starten.",
            ["KrWaitingForDalamud"] = "Warte darauf, dass Dalamud installiert wird (bis zu {0} Minuten). Dieses Fenster bitte offen lassen.",
            ["KrDalamudArrived"] = "Dalamud ist da. Die Installation laeuft weiter.",
            ["KrStillWaiting"] = "Warte seit {0} Minuten.",
            ["KrDalamudWaitGaveUp"] = "Dalamud ist nach {0} Minuten immer noch nicht da. Dieses Programm nach der Installation erneut starten.",
            ["KrDalamudWaitMissing"] = "Zuletzt fehlte: {0}",
            ["KrUpdaterGetByHand"] = "Der Updater liegt noch nicht dort. Er kommt von hier:",
            ["KrRepoRegistered"] = "Repository eingetragen: {0}",
            ["KrRepoMoved"] = "Alte Repository-Adresse entfernt, eingetragen ist jetzt: {0}",
            ["KrRepoListMissing"] = "In der Konfiguration fehlt die Repository-Liste - das Plugin laeuft, aktualisiert sich aber nicht von selbst.",
            ["KrRepoManifestPointed"] = "Die installierte Kopie zeigt jetzt auf dieses Repository.",
            ["KrRepoManifestFailed"] = "Die installierte Kopie konnte nicht auf das Repository umgestellt werden ({0}). Sie laedt weiterhin, aktualisiert sich aber nicht von selbst.",
            ["KrUpdaterWhatItIs1"] = "Der KR-Dalamud-Updater fehlt. Er bringt Dalamud in den koreanischen Client;",
            ["KrUpdaterWhatItIs2"] = "auf der globalen Seite macht das der XIVLauncher. Er stammt von einem anderen",
            ["KrUpdaterWhatItIs3"] = "Autor (MiqoKR) und wird aus dessen Release geladen, nicht von uns weitergegeben.",
            ["AskSetupKrUpdater"] = "Soll der KR-Dalamud-Updater jetzt heruntergeladen werden?",
            ["KrUpdaterSkipped"] = "KR-Dalamud-Updater uebersprungen.",
            ["KrUpdaterCheckingRelease"] = "Suche neuestes Release des KR-Dalamud-Updaters ...",
            ["KrUpdaterDownloading"] = "Lade den KR-Dalamud-Updater herunter ...",
            ["KrUpdaterDownloadLabel"] = "KR-Dalamud-Updater",
            ["KrUpdaterInstalledAt"] = "KR-Dalamud-Updater entpackt nach: {0}",
            ["KrUpdaterLaunched"] = "Der Updater wurde geoeffnet.",
            ["KrUpdaterUnreachable"] = "GitHub nicht erreichbar ({0}). Der Updater muss von Hand geholt werden.",
            ["KrUpdaterTimeout"] = "Zeitueberschreitung bei GitHub. Der Updater muss von Hand geholt werden.",
            ["KrUpdaterNoAsset"] = "Im Release ist kein \"{0}\"-Archiv. Der Updater muss von Hand geholt werden.",
            ["KrUpdaterDownloadFailed"] = "Download des Updaters fehlgeschlagen ({0}).",
            ["KrUpdaterCouldNotWrite"] = "Updater konnte nicht geschrieben werden ({0}).",
            ["KrUpdaterExeMissing"] = "Archiv entpackt, aber es liegt keine EXE hier: {0}",
            ["KrUpdaterUnexpectedError"] = "Unerwarteter Fehler beim Updater ({0}).",
            ["KrLookingForLocalBuild"] = "Suche den lokalen Build des Plugins ...",
            ["KrNoLocalBuild"] = "Kein gebautes Plugin gefunden.",
            ["KrBuildHint"] = @"Bitte zuerst run\build.bat ausfuehren.",
            ["KrGetFromReleasePage"] = "Das Plugin-Archiv gibt es hier:",
            ["KrUsingLocalBuild"] = "Verwende lokalen Build {0} aus {1}",
            ["KrUsingRelease"] = "Verwende Release {0}",
            ["KrReleaseUnreachable"] = "Release konnte nicht abgefragt werden ({0}). Es geht mit dem lokalen Build weiter.",
            ["KrLocalBuildWins"] = "Lokaler Build {0} ist nicht aelter als Release {1} - er wird verwendet.",
            ["KrReleaseDownloadFailed"] = "Download des Releases fehlgeschlagen ({0}).",
            ["KrErrorNoLocalBuild"] = "Fehler: kein lokaler Build vorhanden.",
            ["KrBuildVersionUnreadable"] = "Das gebaute Manifest nennt keine brauchbare Version ({0}). Abbruch - der Ordnername muss eine Version sein.",
            ["KrInstalledAt"] = "Installiert nach: {0}",
            ["KrOldVersionRemoved"] = "Alte Version entfernt: {0}",
            ["KrOldVersionKept"] = "Alte Version blieb liegen: {0} ({1}). Dalamud raeumt sie beim naechsten Start auf.",
            ["KrProfileEntrySeeded"] = "Im Profil eingetragen und aktiviert: {0} ({1})",
            ["KrProfileEntryUpdated"] = "Im Profil aktualisiert und aktiviert: {0} ({1})",
            ["KrDevInstallRemoved"] = "Die fruehere Entwickler-Installation wurde entfernt.",
            ["KrDevInstallStuck"] = "Die fruehere Entwickler-Installation liess sich nicht entfernen: {0} ({1}). Spiel schliessen und erneut ausfuehren - sonst laedt dasselbe Plugin zweimal.",
            ["LanguageKoreanButton"] = "한국어",
        },
        [English] = new Dictionary<string, string>
        {
            ["WarnPrefix"] = "Warning: ",
            ["ErrorPrefix"] = "Error: ",
            ["UnknownVersion"] = "unknown",

            ["InstallerHeader"] = "FF14 Accessibility – Installer and Updater (version {0}).",
            ["CheckingXivLauncher"] = "Checking for XIVLauncher ...",
            ["XivLauncherFound"] = "XIVLauncher found.",
            ["SummaryHeader"] = "=== Summary ===",
            ["SummaryAccessibility"] = "FF14 Accessibility: {0}",
            ["SummaryVnavmesh"] = "vnavmesh (auto-walk): {0}",
            ["SummaryDungeonPaths"] = "Dungeon routes: {0}",

            // Route files for the "dungeon" category
            ["CheckingDungeonPaths"] = "Downloading the route files for the \"dungeon\" category ...",
            ["DungeonPathsWritten"] = "Wrote {0} route files to {1}",
            ["DungeonPathsSummary"] = "{0} routes loaded",
            ["DungeonPathsUnreachable"] = "The route files cannot be reached right now ({0}). The plugin will fetch them itself on first start.",
            ["DungeonPathsTimeout"] = "Timed out while downloading the route files. The plugin will fetch them itself on first start.",
            ["DungeonPathsNothingInArchive"] = "The downloaded archive contains no route file at all - the source has changed its layout.",
            ["DungeonPathsArchiveTooBig"] = "The archive is unexpectedly large and was not unpacked.",
            ["DungeonPathsUnexpectedError"] = "The route files could not be written: {0}",
            ["UnexpectedError"] = "Unexpected error: {0}",
            ["NoPartialWrite"] = "Nothing incomplete was written that could damage your system.",
            ["UnexpectedErrorWhere"] = "How far it got is in the status messages above.",

            ["XivLauncherNotInstalled1"] = "XIVLauncher is not installed (folder not found:",
            ["XivLauncherNotInstalled2"] = "  {0}).",
            ["XivLauncherNeeded"] = "XIVLauncher is required because it loads Dalamud, the foundation the plugin runs on.",
            ["DownloadingXivLauncherAuto"] = "Downloading the latest XIVLauncher version and installing it automatically ...",
            ["GitHubUnreachable"] = "GitHub is unreachable ({0}). Please check your internet connection.",
            ["InstallXivLauncherManually1"] = "Alternatively, install XIVLauncher manually from https://goatcorp.github.io/ and",
            ["RunProgramAgain"] = "run this program again afterwards.",
            ["TimeoutFetchXivLauncher"] = "Timed out while checking the XIVLauncher version. Please check your internet connection.",
            ["NoXivLauncherSetupFound"] = "No XIVLauncher setup found in the latest release.",
            ["InstallXivLauncherManually2"] = "Please install XIVLauncher manually from https://goatcorp.github.io/ .",
            ["DownloadingXivLauncherVersion"] = "Downloading XIVLauncher {0} ({1}) ...",
            ["DownloadFailedInstallManually"] = "Download failed ({0}). Please install XIVLauncher manually from",
            ["UrlAndRunAgain"] = "https://goatcorp.github.io/ and run this program again afterwards.",
            ["TimeoutDownloadRetry"] = "Timed out during download. Please check your internet connection and try again.",
            ["XivLauncherSaveFailed"] = "Could not save the XIVLauncher setup file: {0}",
            ["InstallingXivLauncherSilent"] = "Installing XIVLauncher automatically in the background (--silent) ...",
            ["XivLauncherInstallStarted"] = "The XIVLauncher installation was started and should be finished by now.",
            ["AutoInstallNotConfirmed"] = "The automatic installation could not be confirmed ({0}).",
            ["RunSetupManuallyHint"] = "If XIVLauncher did not start, run the file manually:",
            ["LoginHint1"] = "Please log in to XIVLauncher now, enable Dalamud in the settings,",
            ["LoginHint2"] = "and start the game ONCE. Then run this installer again",
            ["LoginHint3"] = "to set up the accessibility plugin.",

            // Installer self-update
            ["CheckingInstallerVersion"] = "Checking whether a newer installer version exists ...",
            ["NoInstallerManifest"] = "No installer version info found in the release - skipping the check.",
            ["InstallerCheckFailed"] = "Could not check the installer version ({0}). Carrying on as usual.",
            ["InstallerManifestUnreadable"] = "The installer version info could not be read - skipping the check.",
            ["InstallerUpToDate"] = "The installer is up to date (version {0}).",
            ["InstallerAssetMissing"] = "The new installer file ({0}) is missing from the release - skipping the update.",
            ["InstallerOwnPathUnknown"] = "Could not determine this program's own path - skipping the installer update.",
            ["InstallerUpdateAvailable"] = "A newer installer version is available: {0} (you have {1}).",
            ["InstallerUpdateQuestion"] =
                "A newer version of the installer is available ({0}).\n\n" +
                "Download and start it now? The download is about {1} megabytes.\n\n" +
                "The installer will close briefly and reopen automatically. " +
                "The installation then continues on its own.\n\n" +
                "Yes = update now, No = keep using the current version.",
            ["InstallerUpdateDeclined"] = "Installer update skipped. Continuing with the current version.",
            ["DownloadingInstaller"] = "Downloading installer version {0} ...",
            ["InstallerDownloadLabel"] = "Installer",
            ["InstallerDownloadFailed"] = "Could not download the installer update ({0}). Continuing with the current version.",
            ["InstallerHashOk"] = "Checksum of the new installer file matches.",
            ["InstallerNoHash"] = "No checksum published in the release - the download is accepted unverified.",
            ["InstallerHashMismatch"] = "The checksum of the downloaded installer does NOT match. Update aborted, continuing with the current version.",
            ["InstallerStartFailed"] = "The new installer could not be started ({0}). Continuing with the current version.",
            ["InstallerRestarting"] = "Updating the installer to version {0}. This window closes now and reopens automatically in a moment ...",
            ["InstallerUpdatedTo"] = "The installer was updated to version {0}. The installation continues automatically.",
            ["InstallerUpdatedMessage"] =
                "The installer was updated to version {0} and restarted.\n\n" +
                "After you confirm, the installation continues automatically - there is nothing else you need to do.",
            ["SelfUpdateNoOwnPath"] =
                "Could not determine this program's own path. The old installer file stays as it is; " +
                "this window continues from the temporary folder.",
            ["SelfUpdateReplaceFailed"] =
                "Could not replace the existing installer file:\n{0}\n\nReason: {1}\n\n" +
                "The installation can still continue. If you want to keep the new version permanently, " +
                "download FF14AccessibilityInstaller.exe manually from the latest release once.",
            ["SelfUpdateRestartFailed"] =
                "The installer file was updated but could not be started automatically:\n{0}\n\nReason: {1}\n\n" +
                "Please start it manually.",

            ["CheckingAccessibilityVersion"] = "Checking for the latest version of FF14 Accessibility ...",
            ["NoAccessibilityAssetFound"] = "No matching release package found for FF14 Accessibility.",
            ["ErrorNoReleaseAsset"] = "Error (no release asset found)",
            ["AccessibilityUpToDate"] = "FF14 Accessibility is up to date (version {0}).",
            ["UpToDateShort"] = "up to date (version {0})",
            ["DownloadingAccessibility"] = "Downloading FF14 Accessibility {0} ...",
            ["AccessibilityUpdated"] = "FF14 Accessibility updated to version {0}.",
            ["AccessibilityInstalled"] = "FF14 Accessibility installed (version {0}).",
            ["UpdatedToShort"] = "updated to {0}",
            ["NewlyInstalledShort"] = "newly installed, version {0}",
            ["CouldNotWritePluginFiles"] = "Could not write plugin files: {0}",
            ["CloseGameAndLauncher"] = "Please close FINAL FANTASY XIV and XIVLauncher completely, then try again.",
            ["ErrorFilesLocked"] = "Error (files locked – please close the game/launcher)",
            ["AccessibilityGitHubUnreachable"] = "FF14 Accessibility: GitHub is unreachable ({0}).",
            ["ErrorNoNetworkGitHub"] = "Error (no network / GitHub unreachable)",
            ["AccessibilityDownloadTimeout"] = "FF14 Accessibility: Timed out during download.",
            ["ErrorTimeout"] = "Error (timed out)",
            ["AccessibilityUnexpectedError"] = "FF14 Accessibility: Unexpected error ({0}).",
            ["ErrorGeneric"] = "Error",

            ["CheckingVnavmeshVersion"] = "Checking for the latest version of vnavmesh (auto-walk) ...",
            ["VnavmeshPunishUnreachable"] = "vnavmesh: puni.sh is unreachable ({0}). Auto-walk remains unchanged.",
            ["ErrorNoNetworkPunish"] = "Error (no network / puni.sh unreachable)",
            ["VnavmeshPunishTimeout"] = "vnavmesh: Timed out contacting puni.sh.",
            ["VnavmeshNotFound"] = "vnavmesh not found in the puni.sh repository.",
            ["ErrorNotFound"] = "Error (not found)",
            ["VnavmeshNoDownloadLink"] = "vnavmesh: no download link found in the repository.",
            ["ErrorNoDownloadLink"] = "Error (no download link)",
            ["VnavmeshUpToDate"] = "vnavmesh is up to date (version {0}).",
            ["AutoWalkNeedsVnav1"] = "The auto-walk feature (walking to targets automatically) needs the separate",
            ["AutoWalkNeedsVnav2"] = "vnavmesh plugin. It comes from a different author (veyn) and is loaded from",
            ["AutoWalkNeedsVnav3"] = "the original source, not redistributed by us.",
            ["AskSetupVnavmesh"] = "Set up vnavmesh now for auto-walk?",
            ["VnavmeshSkipped"] = "vnavmesh skipped. Everything except auto-walk still works.",
            ["SkippedShort"] = "skipped",
            ["OkShort"] = "set up",
            ["ErrorShort"] = "failed",
            ["SummaryPlayLauncher"] = "Play shortcut: {0}",
            ["PlayLauncherInstalling"] = "Setting up the shortcut that starts the game and the updater together ...",
            ["PlayLauncherMissingResource"] = "The launcher is not inside this EXE - the build did not embed it.",
            ["PlayLauncherFailed"] = "The launcher could not be written out: {0}",
            ["PlayLauncherShortcutMade"] = "Shortcut created: {0}",
            ["PlayLauncherShortcutFailed"] = "The shortcut could not be created: {0}",
            ["PlayLauncherRunItDirectly"] = "The launcher itself is here and can be started directly:",
            ["PlayLauncherReady"] = "From now on the {0} shortcut starts the game and the updater together. All that is left is logging in.",
            ["DownloadingVnavmesh"] = "Downloading vnavmesh {0} ...",
            ["VnavmeshUpdated"] = "vnavmesh updated to version {0}.",
            ["VnavmeshSetup"] = "vnavmesh set up (version {0}).",
            ["NewlySetupShort"] = "newly set up, version {0}",
            ["VnavmeshCouldNotWriteFiles"] = "vnavmesh: Could not write files: {0}",
            ["VnavmeshDownloadFailed"] = "vnavmesh: Download failed ({0}).",
            ["ErrorNoNetwork"] = "Error (no network)",
            ["VnavmeshDownloadTimeout"] = "vnavmesh: Timed out during download.",
            ["VnavmeshUnexpectedError"] = "vnavmesh: Unexpected error ({0}).",

            ["ConfigNotExist1"] = "dalamudConfig.json does not exist yet – Dalamud only creates it on the",
            ["ConfigNotExist2"] = "first game start. Start the game ONCE via XIVLauncher (with",
            ["ConfigNotExist3"] = "Dalamud enabled) and run this installer again afterwards so",
            ["ConfigNotExist4"] = "the plugins can be enabled.",
            ["ConfigMissingReturn"] = "dalamudConfig.json is still missing – please start the game once and run the installer again.",
            ["ConfigReadFailed"] = "dalamudConfig.json could not be read: {0}",
            ["ConfigReadFailedReturn"] = "Error reading dalamudConfig.json (file locked?).",
            ["ConfigParseFailed"] = "dalamudConfig.json could not be parsed ({0}).",
            ["ConfigNotTouching"] = "I will not touch it. Please get in touch – manual editing is safer here.",
            ["ConfigInvalidReturn"] = "Error: dalamudConfig.json is invalid, not modified.",
            ["ConfigUnexpectedStructure"] = "Unexpected configuration structure (DevPluginLoadLocations missing).",
            ["ConfigSafetyNoChange1"] = "For safety, nothing will be changed. Please start the game once and",
            ["ConfigSafetyNoChange2"] = "try again.",
            ["ConfigUnexpectedStructureReturn"] = "Error: unexpected dalamudConfig.json structure, not modified.",
            ["ConfigUpdated"] = "Configuration updated (backup: {0}).",
            ["ProfileStructureUnexpected"] = "Unexpected configuration structure (DefaultProfile missing) – plugins could not be enabled. Please get in touch.",
            ["ProfileStructureUnexpectedReturn"] = "Error: plugins registered, but enabling was not possible (DefaultProfile missing).",
            ["PluginsRegisteredEnabledReturn"] = "Plugins registered and enabled.",
            ["ConfigWriteFailed"] = "dalamudConfig.json could not be written: {0}",
            ["ConfigWriteFailedReturn"] = "Error writing dalamudConfig.json (file locked?).",

            ["DownloadProgress"] = "{0}: {1} % ...",

            ["PlayShortcutName"] = "Play with FF14 Accessibility",
            ["PlayNoUpdater"] = "The Korean Dalamud updater could not be started: {0}. Please run the installer once more.",
            ["PlayNoGame"] = "The game could not be started. The shortcut is missing: {0}",
            ["WindowTitle"] = "FF14 Accessibility – Installer",
            ["MainTitleWithVersion"] = "FF14 Accessibility – Installer and Updater (version {0})",
            ["MainTitleAccessibleName"] = "FF14 Accessibility Installer, version {0}",
            ["LogBoxAccessibleName"] = "Status messages",
            ["LogBoxAccessibleDescription"] = "Progress and result messages from the installer, navigable with arrow keys.",
            ["InstallButtonText"] = "Install / Update",
            ["InstallButtonAccessibleName"] = "Install or update",
            ["ExitButtonText"] = "Exit",
            ["ExitButtonAccessibleName"] = "Exit",
            ["OperationCompleted"] = "Operation completed. See the log area in the window for details.",

            ["LanguageDialogTitle"] = "Sprache wählen / Choose language",
            ["LanguageGermanButton"] = "Deutsch",
            ["LanguageEnglishButton"] = "English",
            ["KrCheckingProfile"] = "Checking the Korean profile ...",
            ["KrProfileRoot"] = "Profile root: {0}  (decided by: {1})",
            ["KrProfileFound"] = "Profile found.",
            ["KrProfileCreated"] = "Created the missing pieces: {0}",
            ["KrRuntimeVariableSet"] = "DALAMUD_RUNTIME set to: {0}",
            ["KrRuntimeNeedsRestart"] = "The game has to be started fresh after this - a process inherits its environment at launch.",
            ["KrRuntimeNoDotnet"] = "No .NET found ({0}). DALAMUD_RUNTIME stays empty, and without it Dalamud never starts inside the game - nothing reports that.",
            ["KrRuntimeGetDotnet"] = "Install the .NET desktop runtime and run this program again.",
            ["DotnetPresent"] = ".NET {0} desktop runtime is present: {1}",
            ["DotnetMissing"] = ".NET {0} desktop runtime is missing ({1}). Without it Dalamud never starts inside the game.",
            ["AskInstallDotnet"] = "Download and install the .NET {0} desktop runtime now?",
            ["DotnetInstallDeclined"] = "Not installed. The game will start, the plugin will stay silent.",
            ["DotnetSkipped"] = ".NET install is turned off via FF14ACC_SKIP_DOTNET.",
            ["DotnetLabel"] = ".NET desktop runtime",
            ["DotnetDownloading"] = "Downloading the .NET desktop runtime ...",
            ["DotnetDownloadFailed"] = "Downloading the .NET runtime failed: {0}",
            ["DotnetGetByHand"] = "The runtime can be fetched by hand here:",
            ["DotnetInstalling"] = "Installing the .NET desktop runtime. This takes a moment; please confirm the Windows prompt.",
            ["DotnetInstalled"] = ".NET {0} desktop runtime installed.",
            ["DotnetRebootRequired"] = "Windows wants a restart before the runtime can be used.",
            ["DotnetInstallCancelled"] = "The Windows prompt was dismissed, so the runtime was not installed.",
            ["DotnetInstallFailed"] = "Installing the .NET runtime failed (code {0}).",
            ["KrDalamudMissing"] = "Korean Dalamud is not installed yet.",
            ["KrDalamudGetIt"] = "Run the KR Dalamud updater first and press \"Check Update\":",
            ["KrDalamudThenCheckUpdate"] = "Then start this program again.",
            ["KrWaitingForDalamud"] = "Waiting for Dalamud to be installed (up to {0} minutes). Please leave this window open.",
            ["KrDalamudArrived"] = "Dalamud is there. The installation continues.",
            ["KrStillWaiting"] = "Waiting for {0} minutes now.",
            ["KrDalamudWaitGaveUp"] = "Dalamud is still not there after {0} minutes. Start this program again once it is installed.",
            ["KrDalamudWaitMissing"] = "What was still missing: {0}",
            ["KrUpdaterGetByHand"] = "The updater is not there yet. It comes from here:",
            ["KrRepoRegistered"] = "Repository registered: {0}",
            ["KrRepoMoved"] = "The old repository address was removed; the one registered now is: {0}",
            ["KrRepoListMissing"] = "The configuration carries no repository list - the plugin runs, but it will not update itself.",
            ["KrRepoManifestPointed"] = "The installed copy now points at that repository.",
            ["KrRepoManifestFailed"] = "Could not point the installed copy at the repository ({0}). It still loads, but it will not update itself.",
            ["KrUpdaterWhatItIs1"] = "The KR Dalamud updater is missing. It puts Dalamud into the Korean client;",
            ["KrUpdaterWhatItIs2"] = "on the global side XIVLauncher does that. It comes from a different author",
            ["KrUpdaterWhatItIs3"] = "(MiqoKR) and is loaded from their release, not redistributed by us.",
            ["AskSetupKrUpdater"] = "Download the KR Dalamud updater now?",
            ["KrUpdaterSkipped"] = "Skipped the KR Dalamud updater.",
            ["KrUpdaterCheckingRelease"] = "Looking for the latest KR Dalamud updater release ...",
            ["KrUpdaterDownloading"] = "Downloading the KR Dalamud updater ...",
            ["KrUpdaterDownloadLabel"] = "KR Dalamud updater",
            ["KrUpdaterInstalledAt"] = "KR Dalamud updater unpacked to: {0}",
            ["KrUpdaterLaunched"] = "The updater has been opened.",
            ["KrUpdaterUnreachable"] = "GitHub is unreachable ({0}). The updater has to be fetched by hand.",
            ["KrUpdaterTimeout"] = "GitHub timed out. The updater has to be fetched by hand.",
            ["KrUpdaterNoAsset"] = "The release carries no \"{0}\" archive. The updater has to be fetched by hand.",
            ["KrUpdaterDownloadFailed"] = "Downloading the updater failed ({0}).",
            ["KrUpdaterCouldNotWrite"] = "Could not write the updater ({0}).",
            ["KrUpdaterExeMissing"] = "The archive extracted, but there is no EXE here: {0}",
            ["KrUpdaterUnexpectedError"] = "Unexpected error while fetching the updater ({0}).",
            ["KrLookingForLocalBuild"] = "Looking for the locally built plugin ...",
            ["KrNoLocalBuild"] = "No built plugin found.",
            ["KrBuildHint"] = @"Run run\build.bat first.",
            ["KrGetFromReleasePage"] = "The plugin archive lives here:",
            ["KrUsingLocalBuild"] = "Using local build {0} from {1}",
            ["KrUsingRelease"] = "Using release {0}",
            ["KrReleaseUnreachable"] = "Could not check the release ({0}). Carrying on with the local build.",
            ["KrLocalBuildWins"] = "Local build {0} is not older than release {1} - using the local build.",
            ["KrReleaseDownloadFailed"] = "Downloading the release failed ({0}).",
            ["KrErrorNoLocalBuild"] = "Error: no local build available.",
            ["KrBuildVersionUnreadable"] = "The built manifest carries no usable version ({0}). Stopping - the folder name has to be a version.",
            ["KrInstalledAt"] = "Installed to: {0}",
            ["KrOldVersionRemoved"] = "Removed the old version: {0}",
            ["KrOldVersionKept"] = "Could not remove the old version: {0} ({1}). Dalamud cleans it up on the next start.",
            ["KrProfileEntrySeeded"] = "Registered in the profile and enabled: {0} ({1})",
            ["KrProfileEntryUpdated"] = "Updated in the profile and enabled: {0} ({1})",
            ["KrDevInstallRemoved"] = "Removed the earlier dev-plugin installation.",
            ["KrDevInstallStuck"] = "Could not remove the earlier dev-plugin installation: {0} ({1}). Close the game and run this again - otherwise the same plugin loads twice.",
            ["LanguageKoreanButton"] = "한국어",
        },

        [Korean] = new Dictionary<string, string>
        {
            // 한국어는 KR 흐름이 실제로 보여주는 키만 갖는다. 나머지는 Get()이
            // 영어로 떨어뜨린다 - 안 쓰는 문장 130개를 번역해 두면 그게 낡는다.
            //
            // 말투는 습니다체다 (2026-08-19 사용자 결정, W-56). 모드가 게임 안에서
            // 내는 것은 상태 보고라 명사형이지만(ko-localization 스킬), 이 창이
            // 내는 것은 절차 안내다 - 무엇을 하는 중이고 다음에 무엇을 하라는 말이라
            // 사용 안내 문서와 성격이 같고, 실제로 그 문서가 여기 문장을 인용한다.
            // 글자 수로 정한 것이 아니다. 짧게 쓰는 것 자체는 목적이 아니고
            // 짧으면서 명확한 것이 목적이다 (2026-08-20).
            ["WarnPrefix"] = "경고: ",
            ["ErrorPrefix"] = "실패: ",
            ["UnknownVersion"] = "알 수 없음",
            ["InstallerHeader"] = "FF14 접근성 모드 설치 프로그램 (한국 서버용, 버전 {0})",

            // 설치 프로그램 자기 업데이트
            ["CheckingInstallerVersion"] = "설치 프로그램의 새 버전이 있는지 확인합니다 ...",
            ["NoInstallerManifest"] = "릴리스에 설치 프로그램 버전 정보가 없습니다 - 확인을 건너뜁니다.",
            ["InstallerCheckFailed"] = "설치 프로그램 버전을 확인하지 못했습니다: {0}. 설치는 그대로 이어집니다.",
            ["InstallerManifestUnreadable"] = "설치 프로그램 버전 정보를 읽지 못했습니다 - 확인을 건너뜁니다.",
            ["InstallerUpToDate"] = "설치 프로그램 {0} - 최신 버전입니다.",
            ["InstallerAssetMissing"] = "새 설치 프로그램 파일({0})이 릴리스에 없습니다 - 업데이트를 건너뜁니다.",
            ["InstallerOwnPathUnknown"] = "이 프로그램 자신의 경로를 알아내지 못했습니다 - 설치 프로그램 업데이트를 건너뜁니다.",
            ["InstallerUpdateAvailable"] = "새 설치 프로그램 버전이 있습니다: {0} (설치된 것은 {1}).",
            ["InstallerUpdateQuestion"] =
                "설치 프로그램의 새 버전이 있습니다({0}).\n\n" +
                "지금 내려받아 실행할까요? 내려받는 크기는 약 {1}메가바이트입니다.\n\n" +
                "설치 프로그램이 잠깐 닫혔다가 자동으로 다시 실행됩니다. " +
                "그 다음 설치가 알아서 이어집니다.\n\n" +
                "예 = 지금 업데이트, 아니오 = 지금 버전 그대로 진행.",
            ["InstallerUpdateDeclined"] = "설치 프로그램 업데이트를 건너뛰었습니다. 지금 버전 그대로 이어서 진행합니다.",
            ["DownloadingInstaller"] = "설치 프로그램 {0} 내려받는 중 ...",
            ["InstallerDownloadLabel"] = "설치 프로그램",
            ["InstallerDownloadFailed"] = "설치 프로그램 업데이트를 내려받지 못했습니다: {0}. 지금 버전 그대로 이어서 진행합니다.",
            ["InstallerHashOk"] = "새 설치 프로그램 파일의 체크섬이 맞습니다.",
            ["InstallerNoHash"] = "릴리스에 체크섬이 없습니다 - 내려받은 파일을 검사 없이 씁니다.",
            ["InstallerHashMismatch"] = "내려받은 설치 프로그램의 체크섬이 맞지 않습니다. 업데이트를 중단하고 지금 버전 그대로 이어서 진행합니다.",
            ["InstallerStartFailed"] = "새 설치 프로그램을 실행하지 못했습니다: {0}. 지금 버전 그대로 이어서 진행합니다.",
            ["InstallerRestarting"] = "설치 프로그램을 {0}으로 업데이트합니다. 이 창은 지금 닫히고 잠시 뒤 자동으로 다시 실행됩니다 ...",
            ["InstallerUpdatedTo"] = "설치 프로그램을 {0}으로 업데이트했습니다. 설치는 자동으로 이어집니다.",
            ["InstallerUpdatedMessage"] =
                "설치 프로그램을 {0}으로 업데이트하고 다시 실행했습니다.\n\n" +
                "확인을 누르면 설치가 자동으로 이어집니다 - 더 하실 일은 없습니다.",
            ["SelfUpdateNoOwnPath"] =
                "이 프로그램 자신의 경로를 알아내지 못했습니다. 옛 설치 프로그램 파일은 그대로 남고, " +
                "이 창은 임시 폴더에서 이어서 동작합니다.",
            ["SelfUpdateReplaceFailed"] =
                "기존 설치 프로그램 파일을 바꾸지 못했습니다:\n{0}\n\n이유: {1}\n\n" +
                "설치는 그대로 이어서 할 수 있습니다. 새 버전을 계속 쓰려면 " +
                "최신 릴리스에서 FF14AccessibilityInstaller-KR.exe를 한 번 직접 받으세요.",
            ["SelfUpdateRestartFailed"] =
                "설치 프로그램 파일은 업데이트했는데 자동으로 실행하지 못했습니다:\n{0}\n\n이유: {1}\n\n" +
                "직접 실행해주세요.",

            ["KrCheckingProfile"] = "한국 서버 프로필을 확인합니다 ...",
            ["KrProfileRoot"] = "프로필 루트: {0}  (이 경로의 출처: {1})",
            ["KrProfileFound"] = "프로필이 존재합니다.",
            ["KrProfileCreated"] = "프로필에 새로 만들었습니다: {0}",
            ["KrRuntimeVariableSet"] = "DALAMUD_RUNTIME을 설정했습니다: {0}",
            ["KrRuntimeNeedsRestart"] = "게임을 새로 켜야 반영됩니다. 켜져 있으면 껐다가 다시 켜 주세요.",
            ["KrRuntimeNoDotnet"] = ".NET을 찾지 못했습니다: {0}. DALAMUD_RUNTIME을 설정하지 못했고, 이 값이 없으면 게임 안에서 Dalamud가 뜨지 않습니다. 아무 데서도 오류로 알려 주지 않습니다.",
            ["KrRuntimeGetDotnet"] = ".NET 데스크톱 런타임을 설치한 뒤 이 프로그램을 다시 실행해주세요.",
            ["DotnetPresent"] = ".NET {0} 데스크톱 런타임이 설치되어 있습니다: {1}",
            ["DotnetMissing"] = ".NET {0} 데스크톱 런타임이 없습니다: {1}. 이것이 없으면 게임 안에서 Dalamud가 뜨지 않습니다.",
            ["AskInstallDotnet"] = ".NET {0} 데스크톱 런타임을 지금 내려받아 설치하시겠습니까?",
            ["DotnetInstallDeclined"] = "설치하지 않았습니다. 게임은 켜지지만 모드는 뜨지 않습니다.",
            ["DotnetSkipped"] = "FF14ACC_SKIP_DOTNET이 설정되어 있어 .NET 설치를 건너뜁니다.",
            ["DotnetLabel"] = ".NET 데스크톱 런타임",
            ["DotnetDownloading"] = ".NET 데스크톱 런타임을 내려받습니다 ...",
            ["DotnetDownloadFailed"] = ".NET 런타임을 내려받지 못했습니다: {0}",
            ["DotnetGetByHand"] = "다음 주소에서 직접 내려받아 설치해주세요:",
            ["DotnetInstalling"] = ".NET 데스크톱 런타임을 설치합니다. 시간이 걸리며, 윈도우 권한 요청 창이 뜨면 예를 눌러주세요.",
            ["DotnetInstalled"] = ".NET {0} 데스크톱 런타임을 설치했습니다.",
            ["DotnetRebootRequired"] = "런타임을 쓰려면 윈도우를 다시 시작해야 합니다.",
            ["DotnetInstallCancelled"] = "윈도우 권한 요청을 취소해서 런타임을 설치하지 못했습니다.",
            ["DotnetInstallFailed"] = ".NET 런타임 설치가 실패했습니다. 종료 코드 {0}.",
            ["KrDalamudMissing"] = "한국 서버용 Dalamud가 설치되지 않았습니다.",
            ["KrDalamudGetIt"] = "먼저 KR Dalamud 업데이터를 실행해 \"업데이트 확인\"을 눌러주세요:",
            ["KrDalamudThenCheckUpdate"] = "KR Dalamud 업데이터 완료 후 프로그램을 다시 실행해주세요.",
            ["KrWaitingForDalamud"] = "Dalamud 설치가 끝나기를 기다리는 중입니다 (최대 {0}분). 이 창은 닫지 마세요.",
            ["KrDalamudArrived"] = "Dalamud가 설치됐습니다. 접근성 모드를 설치하는 동안 이 창을 그대로 두세요.",
            ["KrStillWaiting"] = "{0}분째 기다리는 중입니다.",
            ["KrDalamudWaitGaveUp"] = "{0}분을 기다렸는데 Dalamud가 아직 설치되지 않았습니다. 설치가 끝나면 이 프로그램을 다시 실행해주세요.",
            ["KrDalamudWaitMissing"] = "끝까지 없던 것: {0}",
            ["KrUpdaterGetByHand"] = "업데이터가 아직 그 자리에 없습니다. 여기서 받습니다:",
            ["KrRepoRegistered"] = "저장소 등록 완료: {0}",
            ["KrRepoMoved"] = "옛 저장소 주소를 지우고 새 주소로 등록했습니다: {0}",
            ["KrRepoListMissing"] = "설정에 저장소 목록이 없습니다. 모드는 동작하지만 새 버전을 알아서 받지는 못합니다.",
            ["KrRepoManifestPointed"] = "설치한 모드가 이 저장소에서 업데이트를 받도록 연결했습니다.",
            ["KrRepoManifestFailed"] = "설치한 모드를 저장소에 연결하지 못했습니다: {0}. 모드는 동작하지만 새 버전을 알아서 받지는 못합니다.",
            ["KrUpdaterWhatItIs1"] = "KR Dalamud 업데이터가 없습니다. 게임에 Dalamud를 붙여 주는 프로그램입니다.",
            ["KrUpdaterWhatItIs2"] = "KR Dalamud 업데이터는 제작자 저장소에서 내려받습니다.",
            ["KrUpdaterWhatItIs3"] = "이것이 없으면 모드를 설치해도 게임에 올라오지 않습니다.",
            ["AskSetupKrUpdater"] = "KR Dalamud 업데이터를 지금 받으시겠습니까?",
            ["KrUpdaterSkipped"] = "KR Dalamud 업데이터를 건너뛰었습니다.",
            ["KrUpdaterCheckingRelease"] = "KR Dalamud 업데이터의 최신 버전을 확인합니다 ...",
            ["KrUpdaterDownloading"] = "KR Dalamud 업데이터를 내려받는 중 ...",
            ["KrUpdaterDownloadLabel"] = "KR Dalamud 업데이터",
            ["KrUpdaterInstalledAt"] = "KR Dalamud 업데이터 압축을 풀었습니다: {0}",
            ["KrUpdaterLaunched"] = "KR Dalamud Updater 창 열림.",
            ["KrUpdaterUnreachable"] = "GitHub에 연결하지 못했습니다: {0}. 업데이터는 직접 받아야 합니다.",
            ["KrUpdaterTimeout"] = "GitHub 응답이 없습니다. 업데이터는 직접 받아야 합니다.",
            ["KrUpdaterNoAsset"] = "최신 버전에 \"{0}\" 압축이 없습니다. 업데이터는 직접 받아야 합니다.",
            ["KrUpdaterDownloadFailed"] = "업데이터를 내려받지 못했습니다: {0}",
            ["KrUpdaterCouldNotWrite"] = "업데이터를 저장하지 못했습니다: {0}",
            ["KrUpdaterExeMissing"] = "압축은 풀렸는데 실행 파일이 여기 없습니다: {0}",
            ["KrUpdaterUnexpectedError"] = "업데이터를 받다가 예상하지 못한 오류가 났습니다: {0}",

            ["KrLookingForLocalBuild"] = "플러그인을 찾는 중 ...",
            ["KrNoLocalBuild"] = "빌드된 플러그인이 없습니다.",
            ["KrBuildHint"] = @"먼저 run\build.bat을 실행해주세요.",
            ["KrGetFromReleasePage"] = "모드 압축은 여기서 받습니다:",
            ["KrUsingLocalBuild"] = "로컬 빌드 {0} 사용 ({1})",
            ["KrUsingRelease"] = "릴리스 {0} 사용",
            ["KrReleaseUnreachable"] = "릴리스를 확인하지 못했습니다: {0}. 로컬 빌드로 이어서 진행합니다.",
            ["KrLocalBuildWins"] = "로컬 빌드 {0}을 사용합니다. 릴리스 {1}이 더 새것이 아닙니다.",
            ["KrReleaseDownloadFailed"] = "릴리스를 내려받지 못했습니다: {0}",
            ["KrErrorNoLocalBuild"] = "실패: 빌드된 플러그인이 없습니다.",
            ["KrBuildVersionUnreadable"] = "빌드된 매니페스트에서 버전을 읽지 못했습니다({0}). 폴더 이름이 버전이어야 해서 여기서 멈춥니다.",
            ["KrInstalledAt"] = "설치 위치: {0}",
            ["KrOldVersionRemoved"] = "옛 버전을 지웠습니다: {0}",
            ["KrOldVersionKept"] = "옛 버전을 지우지 못했습니다: {0} ({1}). Dalamud가 다음 실행 때 정리합니다.",
            ["KrProfileEntrySeeded"] = "프로필 등록 완료: {0} ({1})",
            ["KrProfileEntryUpdated"] = "프로필 업데이트 완료: {0} ({1})",
            ["KrDevInstallRemoved"] = "예전 개발용 설치를 걷어냈습니다.",
            ["KrDevInstallStuck"] = "예전 개발용 설치를 지우지 못했습니다: {0} ({1}). 게임을 끄고 다시 실행해주세요. 그대로 두면 같은 플러그인을 두 번 불러옵니다.",

            ["CheckingAccessibilityVersion"] = "접근성 모드 버전 확인 중 ...",
            ["NoAccessibilityAssetFound"] = "릴리스에 접근성 모드 압축이 없습니다.",
            ["AccessibilityUpToDate"] = "접근성 모드 {0} - 최신 버전입니다.",
            ["DownloadingAccessibility"] = "접근성 모드 {0} 내려받는 중 ...",
            ["AccessibilityUpdated"] = "접근성 모드를 {0}으로 업데이트했습니다.",
            ["AccessibilityInstalled"] = "접근성 모드 {0}을 설치했습니다.",
            ["UpdatedToShort"] = "{0}으로 업데이트",
            ["NewlyInstalledShort"] = "{0} 새로 설치",
            ["UpToDateShort"] = "{0} - 최신 버전",
            ["CouldNotWritePluginFiles"] = "플러그인 파일을 저장하지 못했습니다: {0}",
            ["CloseGameAndLauncher"] = "FINAL FANTASY XIV와 업데이터를 완전히 끄고 다시 시도해주세요.",
            ["ErrorFilesLocked"] = "실패: 파일이 잠겨 있습니다.",
            ["AccessibilityUnexpectedError"] = "접근성 모드 처리 중 예상하지 못한 오류: {0}",
            ["ErrorGeneric"] = "실패",
            ["ErrorTimeout"] = "실패: 시간 초과",
            ["ErrorNotFound"] = "실패: 찾지 못함",

            ["CheckingVnavmeshVersion"] = "vnavmesh 버전 확인 ...",
            ["VnavmeshPunishUnreachable"] = "puni.sh 저장소에 연결하지 못했습니다: {0}",
            ["ErrorNoNetworkPunish"] = "실패: puni.sh에 연결하지 못함",
            ["VnavmeshPunishTimeout"] = "puni.sh 응답이 시간 초과됐습니다.",
            ["VnavmeshNotFound"] = "저장소 목록에 vnavmesh가 없습니다.",
            ["VnavmeshNoDownloadLink"] = "vnavmesh 내려받기 주소가 없습니다.",
            ["ErrorNoDownloadLink"] = "실패: 내려받기 주소 없음",
            ["VnavmeshUpToDate"] = "vnavmesh {0} - 최신 버전입니다.",
            ["AutoWalkNeedsVnav1"] = "자동 이동은 vnavmesh 플러그인을 설치해야 동작합니다.",
            ["AutoWalkNeedsVnav2"] = "vnavmesh는 제작자 저장소에서 내려받습니다.",
            ["AutoWalkNeedsVnav3"] = "vnavmesh 플러그인을 설치하지 않아도 자동 이동을 제외한 나머지 기능은 동작합니다.",
            ["AskSetupVnavmesh"] = "vnavmesh를 설치하시겠습니까?",
            ["VnavmeshSkipped"] = "vnavmesh를 건너뛰었습니다.",
            ["SkippedShort"] = "건너뜀",
            ["OkShort"] = "설치됨",
            ["ErrorShort"] = "실패",
            ["SummaryPlayLauncher"] = "플레이 바로가기: {0}",
            ["PlayLauncherInstalling"] = "게임과 업데이터를 함께 켜는 바로가기를 만듭니다 ...",
            ["PlayLauncherMissingResource"] = "이 프로그램 안에 실행 파일이 없습니다. 빌드에서 빠졌습니다.",
            ["PlayLauncherFailed"] = "실행 파일을 놓지 못했습니다: {0}",
            ["PlayLauncherShortcutMade"] = "바로가기를 만들었습니다: {0}",
            ["PlayLauncherShortcutFailed"] = "바로가기를 만들지 못했습니다: {0}",
            ["PlayLauncherRunItDirectly"] = "실행 파일은 다음 경로에 있습니다. 직접 실행하셔도 됩니다.",
            ["PlayLauncherReady"] = "이제 {0} 바로가기를 실행하면 게임과 업데이터가 함께 켜집니다. 게임에서 로그인만 하시면 됩니다.",
            ["DownloadingVnavmesh"] = "vnavmesh {0} 내려받는 중 ...",
            ["VnavmeshUpdated"] = "vnavmesh를 {0}으로 업데이트했습니다.",
            ["VnavmeshSetup"] = "vnavmesh {0}을 설치했습니다.",
            ["NewlySetupShort"] = "{0} 새로 설치",
            ["VnavmeshCouldNotWriteFiles"] = "vnavmesh 파일을 저장하지 못했습니다: {0}",
            ["VnavmeshDownloadFailed"] = "vnavmesh를 내려받지 못했습니다: {0}",
            ["ErrorNoNetwork"] = "실패: 연결하지 못함",
            ["VnavmeshDownloadTimeout"] = "vnavmesh 내려받기가 시간 초과됐습니다.",
            ["VnavmeshUnexpectedError"] = "vnavmesh 처리 중 예상하지 못한 오류: {0}",

            ["ConfigNotExist1"] = "dalamudConfig.json이 없습니다.",
            ["ConfigNotExist2"] = "게임을 한 번 실행해 Dalamud를 붙이면 만들어집니다.",
            ["ConfigNotExist3"] = "그 다음 이 프로그램을 다시 실행해주세요.",
            ["ConfigNotExist4"] = "그래야 플러그인을 켤 수 있습니다.",
            ["ConfigMissingReturn"] = "실패: dalamudConfig.json이 없습니다.",
            ["ConfigReadFailed"] = "dalamudConfig.json을 읽지 못했습니다: {0}",
            ["ConfigReadFailedReturn"] = "실패: dalamudConfig.json을 읽지 못함",
            ["ConfigParseFailed"] = "dalamudConfig.json을 해석하지 못했습니다: {0}",
            ["ConfigNotTouching"] = "손대지 않습니다 - 망가뜨리는 쪽이 더 비쌉니다.",
            ["ConfigInvalidReturn"] = "실패: dalamudConfig.json이 깨져 있습니다.",
            ["ConfigUnexpectedStructure"] = "설정 구조가 예상과 다릅니다 (DevPluginLoadLocations 없음).",
            ["ConfigSafetyNoChange1"] = "안전을 위해 아무것도 바꾸지 않았습니다.",
            ["ConfigSafetyNoChange2"] = "게임을 한 번 실행한 뒤 다시 시도해주세요.",
            ["ConfigUnexpectedStructureReturn"] = "실패: 설정 구조가 예상과 다름",
            ["ConfigUpdated"] = "설정 업데이트 함. 백업: {0}",
            ["ProfileStructureUnexpected"] = "DefaultProfile이 없어 플러그인을 켜지 못했습니다.",
            ["ProfileStructureUnexpectedReturn"] = "실패: 등록은 했으나 켜지 못함 (DefaultProfile 없음)",
            ["PluginsRegisteredEnabledReturn"] = "플러그인을 등록하고 활성화했습니다.",
            ["ConfigWriteFailed"] = "dalamudConfig.json을 저장하지 못했습니다: {0}",
            ["ConfigWriteFailedReturn"] = "실패: dalamudConfig.json을 저장하지 못함 (파일이 잠겼나?)",

            ["SummaryHeader"] = "== 결과 ==",
            ["SummaryAccessibility"] = "접근성 모드: {0}",
            ["SummaryVnavmesh"] = "vnavmesh: {0}",
            ["SummaryDungeonPaths"] = "던전 경로: {0}",

            ["CheckingDungeonPaths"] = "던전 분류에 쓸 경로 파일을 받는 중입니다 ...",
            ["DungeonPathsWritten"] = "경로 파일 {0}개를 {1}에 저장했습니다",
            ["DungeonPathsSummary"] = "경로 {0}개를 받았습니다",
            ["DungeonPathsUnreachable"] = "지금은 경로 파일에 연결할 수 없습니다({0}). 플러그인이 처음 실행될 때 직접 받아 옵니다.",
            ["DungeonPathsTimeout"] = "경로 파일을 받는 중에 시간이 초과되었습니다. 플러그인이 처음 실행될 때 직접 받아 옵니다.",
            ["DungeonPathsNothingInArchive"] = "받은 압축 파일에 경로 파일이 하나도 없습니다. 출처의 구성이 바뀌었습니다.",
            ["DungeonPathsArchiveTooBig"] = "압축 파일이 예상보다 커서 풀지 않았습니다.",
            ["DungeonPathsUnexpectedError"] = "경로 파일을 저장하지 못했습니다: {0}",

            ["UnexpectedError"] = "예상하지 못한 오류: {0}",
            ["NoPartialWrite"] = "중간까지 쓰다 만 것은 없습니다.",
            ["UnexpectedErrorWhere"] = "어디까지 진행됐는지는 위의 진행 상황 줄에서 확인할 수 있습니다.",
            ["DownloadProgress"] = "{0}: {1} 퍼센트 ...",

            ["PlayShortcutName"] = "FF14 접근성 모드로 플레이",
            ["PlayNoUpdater"] = "KR Dalamud 업데이터를 실행하지 못했습니다: {0}. 설치 프로그램을 다시 실행해주세요.",
            ["PlayNoGame"] = "게임을 실행하지 못했습니다. 바로가기가 없습니다: {0}",
            ["WindowTitle"] = "FF14 접근성 모드 설치 프로그램 (한국 서버)",
            ["MainTitleWithVersion"] = "FF14 접근성 모드 설치 프로그램, 한국 서버용 (버전 {0})",
            ["MainTitleAccessibleName"] = "FF14 접근성 모드 설치 프로그램, 한국 서버용, 버전 {0}",
            ["LogBoxAccessibleName"] = "진행 상황",
            ["LogBoxAccessibleDescription"] = "설치 프로그램의 진행과 결과 메시지. 화살표 키로 읽을 수 있습니다.",
            ["InstallButtonText"] = "설치 / 업데이트",
            ["InstallButtonAccessibleName"] = "설치 또는 업데이트",
            ["ExitButtonText"] = "끝내기",
            ["ExitButtonAccessibleName"] = "끝내기",
            ["OperationCompleted"] = "끝났습니다. 자세한 내용은 창의 진행 상황 영역에서 확인할 수 있습니다.",

            ["LanguageDialogTitle"] = "언어 선택 / Choose language",
            ["LanguageGermanButton"] = "Deutsch",
            ["LanguageEnglishButton"] = "English",
            ["LanguageKoreanButton"] = "한국어",
        },
    };
}
