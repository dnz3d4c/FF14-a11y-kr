namespace FF14AccessibilityInstaller;

/// <summary>
/// Small, screenreader-friendly language chooser shown before the main
/// window. Two buttons ("Deutsch" / "English"), full keyboard support
/// (Tab to move focus, Enter/Space to activate), and an AccessibleName on
/// every control. The previously saved language (if any) gets focus by
/// default; otherwise the system UI language decides the pre-focused button.
/// This dialog is always shown - the saved/detected language only controls
/// which button is pre-focused, not an automatic skip.
/// </summary>
public sealed class LanguageDialog : Form
{
    /// <summary>
    /// Starts as the preselected language, not as Korean. Closing the window with
    /// Alt+F4 answers nothing, and the caller saves this value either way - so a
    /// hardcoded default meant that dismissing the dialog silently overwrote a
    /// language the user had chosen earlier.
    /// </summary>
    public string SelectedLanguage { get; private set; }

    private readonly Button _koreanButton;
    private readonly Button _germanButton;
    private readonly Button _englishButton;

    public LanguageDialog(string preselectedLanguage)
    {
        SelectedLanguage = preselectedLanguage;

        Text = Loc.Get("LanguageDialogTitle");
        AccessibleName = Loc.Get("LanguageDialogTitle");
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(360, 210);
        ShowInTaskbar = true;

        var label = new Label
        {
            Text = Loc.Get("LanguageDialogTitle") + ":",
            AccessibleName = Loc.Get("LanguageDialogTitle"),
            AutoSize = false,
            Dock = DockStyle.Top,
            Height = 40,
            TextAlign = ContentAlignment.MiddleCenter,
            TabStop = false,
        };

        var buttonPanel = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            Padding = new Padding(24, 8, 24, 8),
        };

        _koreanButton = new Button
        {
            Text = Loc.Get("LanguageKoreanButton"),
            AccessibleName = Loc.Get("LanguageKoreanButton"),
            AutoSize = false,
            Width = 280,
            Height = 40,
            TabIndex = 0,
        };
        _koreanButton.Click += (_, _) => Choose(Loc.Korean);

        _germanButton = new Button
        {
            Text = Loc.Get("LanguageGermanButton"),
            AccessibleName = Loc.Get("LanguageGermanButton"),
            AutoSize = false,
            Width = 280,
            Height = 40,
            TabIndex = 1,
        };
        _germanButton.Click += (_, _) => Choose(Loc.German);

        _englishButton = new Button
        {
            Text = Loc.Get("LanguageEnglishButton"),
            AccessibleName = Loc.Get("LanguageEnglishButton"),
            AutoSize = false,
            Width = 280,
            Height = 40,
            TabIndex = 2,
        };
        _englishButton.Click += (_, _) => Choose(Loc.English);

        buttonPanel.Controls.Add(_koreanButton);
        buttonPanel.Controls.Add(_germanButton);
        buttonPanel.Controls.Add(_englishButton);

        Controls.Add(buttonPanel);
        Controls.Add(label);

        var preselected = preselectedLanguage switch
        {
            Loc.German => _germanButton,
            Loc.English => _englishButton,
            _ => _koreanButton,
        };
        AcceptButton = preselected;

        Load += (_, _) => preselected.Focus();
    }

    private void Choose(string language)
    {
        SelectedLanguage = language;
        DialogResult = DialogResult.OK;
        Close();
    }
}
