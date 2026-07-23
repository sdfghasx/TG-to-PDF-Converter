[Setup]
AppName=TG to PDF Converter
AppVersion=1.0
AppPublisher=sdfghasx
AppPublisherURL=https://github.com/sdfghasx/TG-to-PDF-Converter
DefaultDirName={autopf}\TG to PDF Converter
DefaultGroupName=TG to PDF Converter
AllowNoIcons=yes
; Папка куда сохранится готовый установщик
OutputDir=Output
; Имя установщика
OutputBaseFilename=TG_to_PDF_Setup_v1.0
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Берем ВСЁ из папки dist\main и кладем в папку установки
Source: "dist\main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TG to PDF Converter"; Filename: "{app}\main.exe"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\TG to PDF Converter"; Filename: "{app}\main.exe"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,TG to PDF Converter}"; Flags: nowait postinstall skipifsilent