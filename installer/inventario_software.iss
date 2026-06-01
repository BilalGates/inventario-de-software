#define MyAppName "Inventario Software Asserta"
#define MyAppExeName "Inventario Software Asserta.exe"
#define MyAppPublisher "Asserta"

[Setup]
AppId={{7F729619-9E0A-4DA5-93F8-3FB41F8A1D4B}
AppName={#MyAppName}
AppVersion=1.0.0
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=Inventario_Software_Asserta_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce
Name: "importhistorical"; Description: "Importar datos historicos Excel/CSV si la base esta vacia"; GroupDescription: "Datos iniciales:"; Flags: unchecked

[Files]
Source: "..\dist\Inventario Software Asserta\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--init-db"; WorkingDir: "{app}"; Flags: waituntilterminated; StatusMsg: "Inicializando base de datos local..."; Check: not WizardIsTaskSelected('importhistorical')
Filename: "{app}\{#MyAppExeName}"; Parameters: "--init-db --import-historical"; WorkingDir: "{app}"; Flags: waituntilterminated; StatusMsg: "Importando datos historicos..."; Tasks: importhistorical
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
