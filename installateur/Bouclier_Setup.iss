; Installateur Bouclier - Inno Setup 6.3+ (https://jrsoftware.org/isinfo.php)
#define AppName "Bouclier"
#define AppVersion "3.1.0"
#define AppPublisher "Polaether"
#define AppURL "https://polaether.polaether.workers.dev/"
#define AppExe "Bouclier.exe"

[Setup]
AppId={{7B2D4C1E-5A3F-4E8B-9C6D-1F0A2B3C4D5E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
; Dossier par défaut dans le profil utilisateur : pas besoin d'administrateur, l'appli peut écrire ses réglages.
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
; Page « choisir le dossier » toujours affichée
DisableDirPage=no
UsePreviousAppDir=yes
OutputDir=..\dist_installateur
OutputBaseFilename=Bouclier_Installer
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
WizardImageFile=wizard_large.bmp,wizard_large_2x.bmp
WizardSmallImageFile=wizard_small.bmp,wizard_small_2x.bmp
WizardImageStretch=yes
Compression=lzma2/ultra
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ShowLanguageDialog=auto
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"; LicenseFile: "licence_fr.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "licence_en.txt"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"; LicenseFile: "licence_es.txt"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Bouclier\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "bouclier_erreur.log"

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
