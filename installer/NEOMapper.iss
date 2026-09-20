#ifndef MyAppVersion
  #define MyAppVersion "4.2.4"
#endif

#define MyAppName "NEOMapper"
#define MyAppPublisher "NEOMapper contributors"
#define MyAppExeName "NEOMapper.exe"

[Setup]
AppId={{D222B444-BB90-49B2-A3BD-E12D52405B85}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=NEOMapper-{#MyAppVersion}-Windows-x64-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\src\neomapper\presentation\data\neomapper_icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
english.Windows10Required=NEOMapper requires Windows 10 or a later version of Windows.
english.Windows64BitRequired=NEOMapper requires a 64-bit version of Windows.
english.MemoryBelowMinimum=This computer has less than 4 GB of physical memory. NEOMapper may not run reliably, especially when generating maps or animations. Installation will continue.
english.MemoryBelowRecommended=This computer has less than 8 GB of physical memory. At least 8 GB is recommended for generating maps and animations.
brazilianportuguese.Windows10Required=O NEOMapper requer o Windows 10 ou uma versao posterior do Windows.
brazilianportuguese.Windows64BitRequired=O NEOMapper requer uma versao de 64 bits do Windows.
brazilianportuguese.MemoryBelowMinimum=Este computador tem menos de 4 GB de memoria fisica. O NEOMapper pode nao funcionar de forma confiavel, especialmente ao gerar mapas ou animacoes. A instalacao continuara.
brazilianportuguese.MemoryBelowRecommended=Este computador tem menos de 8 GB de memoria fisica. Recomendamos pelo menos 8 GB para gerar mapas e animacoes.
spanish.Windows10Required=NEOMapper requiere Windows 10 o una version posterior de Windows.
spanish.Windows64BitRequired=NEOMapper requiere una version de Windows de 64 bits.
spanish.MemoryBelowMinimum=Este equipo tiene menos de 4 GB de memoria fisica. NEOMapper podria no funcionar de forma fiable, especialmente al generar mapas o animaciones. La instalacion continuara.
spanish.MemoryBelowRecommended=Este equipo tiene menos de 8 GB de memoria fisica. Se recomiendan al menos 8 GB para generar mapas y animaciones.

[Code]
function GetPhysicallyInstalledSystemMemory(var TotalMemoryInKilobytes: Int64): Boolean;
  external 'GetPhysicallyInstalledSystemMemory@kernel32.dll stdcall setuponly';

function InitializeSetup(): Boolean;
var
  WindowsVersion: TWindowsVersion;
  TotalMemoryInKilobytes: Int64;
  TotalMemoryInGigabytes: Integer;
begin
  Result := False;
  GetWindowsVersionEx(WindowsVersion);
  if WindowsVersion.Major < 10 then begin
    MsgBox(CustomMessage('Windows10Required'), mbCriticalError, MB_OK);
    Exit;
  end;
  if not IsWin64 then begin
    MsgBox(CustomMessage('Windows64BitRequired'), mbCriticalError, MB_OK);
    Exit;
  end;

  if GetPhysicallyInstalledSystemMemory(TotalMemoryInKilobytes) then begin
    TotalMemoryInGigabytes := TotalMemoryInKilobytes div 1024 div 1024;
    if TotalMemoryInGigabytes < 4 then
      MsgBox(CustomMessage('MemoryBelowMinimum'), mbError, MB_OK)
    else if TotalMemoryInGigabytes < 8 then
      MsgBox(CustomMessage('MemoryBelowRecommended'), mbInformation, MB_OK);
  end;
  Result := True;
end;

[Files]
Source: "..\dist\NEOMapper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
