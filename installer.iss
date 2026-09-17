; 视频格式转换器 —— 安装向导脚本（Inno Setup 6）
; 特性：安装路径选择向导页、桌面/开始菜单快捷方式、标准卸载器
#define MyAppName "视频格式转换器"
#define MyAppVersion "1.0.0"
#define MyAppExeName "视频格式转换器.exe"

[Setup]
AppId={{8F3B7C2E-59A1-4D6E-B2C0-5A7D9E1F4C62}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=HR Demo
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; 路径选择向导页显式开启（默认开启，此处声明意图）
DisableDirPage=no
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer_out
OutputBaseFilename=视频格式转换器-安装包-v1.0.0
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription=视频格式转换器安装程序

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent