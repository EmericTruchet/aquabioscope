; Installateur Windows d'AquaBioScope (Inno Setup 6).
;
; Installe dans le dossier de l'utilisateur (%LOCALAPPDATA%\Programs), sans
; droits administrateur : c'est ce qui permet a l'application de se mettre a
; jour toute seule (voir src/aquabioscope/updater.py), en relancant ce meme
; installateur en mode silencieux.
;
; Compilation (apres PyInstaller avec AquaBioScope-installer.spec) :
;   iscc /DAppVersion=0.3.1 installer\AquaBioScope.iss
; Resultat : dist\AquaBioScope-Setup.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Ne jamais changer AppId : c'est lui qui fait reconnaitre une installation
; existante (mise a jour au lieu d'une seconde installation).
AppId={{428A1293-3DD7-4443-AD82-3A63179F34F6}
AppName=AquaBioScope
AppVersion={#AppVersion}
AppVerName=AquaBioScope {#AppVersion}
AppPublisher=Emeric Truchet
AppPublisherURL=https://github.com/EmericTruchet/aquabioscope
DefaultDirName={localappdata}\Programs\AquaBioScope
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=AquaBioScope-Setup
SetupIconFile=..\src\aquabioscope\assets\app_icon.ico
UninstallDisplayIcon={app}\AquaBioScope.exe
UninstallDisplayName=AquaBioScope
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Ferme l'application si elle tourne encore (mise a jour lancee depuis l'appli)
CloseApplications=force
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[InstallDelete]
; Repart d'un dossier propre a chaque mise a jour (pas de vieilles DLL qui trainent).
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\AquaBioScope\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\AquaBioScope"; Filename: "{app}\AquaBioScope.exe"
Name: "{autodesktop}\AquaBioScope"; Filename: "{app}\AquaBioScope.exe"; Tasks: desktopicon

[Run]
; Installation normale : case "Lancer AquaBioScope" en fin d'assistant.
Filename: "{app}\AquaBioScope.exe"; Description: "Lancer AquaBioScope"; Flags: nowait postinstall skipifsilent
; Mise a jour silencieuse lancee par l'application : relance automatique.
Filename: "{app}\AquaBioScope.exe"; Flags: nowait; Check: WizardSilent
