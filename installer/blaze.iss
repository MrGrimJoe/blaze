; Blaze installer (Inno Setup 6). Built in CI by .github/workflows/build-blaze-installer.yml:
;   python installer/stage.py --download          -> installer/build/Blaze/ (app + Python + Node + ffmpeg + browser)
;   ISCC /DAppVersion=0.2.0 installer\blaze.iss   -> dist\Blaze_Setup_0.2.0.exe
;
; Everything Blaze needs is inside the installer: no Python, Node.js, ffmpeg or browser to install first, no admin rights,
; nothing written to the registry besides the uninstall entry. Your videos, library and settings live in your own folders and
; are kept when you uninstall.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Blaze"
#define StageDir "build\Blaze"

[Setup]
AppId={{7B1E6C3A-52D8-4F0B-9A64-1C0E5B7D2F83}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Blaze
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=Blaze_Setup_{#AppVersion}
SetupIconFile=assets\blaze.ico
UninstallDisplayIcon={app}\blaze.ico
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardSizePercent=105
WizardImageFile=assets\wizard-large.bmp
WizardSmallImageFile=assets\wizard-small.bmp
LicenseFile={#StageDir}\LICENSE.txt
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
ShowLanguageDialog=no
CloseApplications=yes
SetupLogging=yes
VersionInfoVersion={#AppVersion}.0
VersionInfoDescription={#AppName} setup
VersionInfoProductName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nBlaze turns a plain-text screenplay into an animated, voiced video. It runs on your own computer and works offline; nothing is uploaded unless you choose an AI provider to help write a story.%n%nEverything it needs is included in this installer, together with Blaze Studio, a desktop window that plans and draws a video from a description.
FinishedHeadingLabel=Blaze is ready
FinishedLabelNoIcons=Blaze has been installed. Your videos are saved in your Videos\Blaze folder.
FinishedLabel=Blaze has been installed. Your videos are saved in your Videos\Blaze folder.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Dirs]
; the person's own folders: created for them, and never removed by the uninstaller
Name: "{%USERPROFILE}\Videos\Blaze"; Flags: uninsneveruninstall
Name: "{%USERPROFILE}\Documents\Blaze\library"; Flags: uninsneveruninstall

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\runtime\python\pythonw.exe"; Parameters: """{app}\app\blaze_app.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\blaze.ico"; Comment: "Turn a screenplay into a video"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\runtime\python\pythonw.exe"; Parameters: """{app}\app\blaze_app.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\blaze.ico"; Comment: "Turn a screenplay into a video"; Tasks: desktopicon
Name: "{autoprograms}\{#AppName} Studio"; Filename: "{app}\runtime\python\pythonw.exe"; Parameters: """{app}\app\studio_app.pyw"""; WorkingDir: "{app}\app\studio"; IconFilename: "{app}\blaze.ico"; Comment: "Describe a video and let the studio plan, draw and join it"
Name: "{autoprograms}\{#AppName} videos"; Filename: "{%USERPROFILE}\Videos\Blaze"
Name: "{autoprograms}\{#AppName} examples"; Filename: "{app}\app\examples"

[Run]
Filename: "{app}\runtime\python\pythonw.exe"; Parameters: """{app}\app\blaze_app.pyw"""; WorkingDir: "{app}\app"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; leftovers made while running (compiled Python files, caches); the person's own folders are not under {app}
Type: filesandordirs; Name: "{app}"
