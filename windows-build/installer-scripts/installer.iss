; Inno Setup 6.x — 工艺参数在线分析与调优系统 安装脚本
; 编译方式：使用 Inno Setup Compiler 打开本文件 → Build → 生成 setup.exe

#define AppName "工艺参数在线分析与调优系统"
#define AppNameEn "ProcessOpt"
#define AppVersion "0.1.0"
#define AppPublisher "ProcessOpt Team"
#define AppExeName "open-web.bat"

[Setup]
; 应用 ID — 首次生成后固定，用于识别升级
AppId={{7E9B4C5E-8F1A-4D5C-9B3E-2A6F8D7E1C4B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppMutex=ProcessOptInstallerMutex

; 默认安装到 Program Files\ProcessOpt
DefaultDirName={autopf}\{#AppNameEn}
DefaultGroupName={#AppName}

; 输出的安装程序
OutputDir=..\build\output
OutputBaseFilename=ProcessOpt-Setup-{#AppVersion}-x64
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4

; 需要管理员权限（注册 Windows 服务）
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=

; 只支持 x64 Windows
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; 界面
WizardStyle=modern
WizardSizePercent=120
DisableProgramGroupPage=yes
ShowLanguageDialog=no
LicenseFile=
InfoBeforeFile=
InfoAfterFile=..\installer-scripts\README.txt

; 卸载
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\app\web\dist\favicon.ico
CreateUninstallRegKey=yes
Uninstallable=yes

; 最小系统要求
MinVersion=10.0

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
; 主内容：整个 build\ProcessOpt\ 目录
Source: "..\build\ProcessOpt\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Dirs]
; 数据/日志目录（可写）
Name: "{app}\logs"; Permissions: users-modify
Name: "{app}\postgresql\data"; Permissions: users-modify
Name: "{app}\nats\data"; Permissions: users-modify

[Run]
; 安装完成后自动执行：
; 1. 初始化 PostgreSQL 数据目录 + 应用 SQL 迁移
Filename: "{app}\scripts\init-db.bat"; StatusMsg: "初始化数据库..."; Flags: runhidden waituntilterminated

; 2. 注册并启动 Windows 服务
Filename: "{app}\scripts\install-services.bat"; StatusMsg: "注册 Windows 服务并启动..."; Flags: runhidden waituntilterminated

; 3. （可选）安装完成后打开浏览器
Filename: "{app}\scripts\open-web.bat"; Description: "启动后打开系统"; Flags: postinstall skipifsilent shellexec

[UninstallRun]
; 卸载时先停止并移除服务
Filename: "{app}\scripts\uninstall-services.bat"; RunOnceId: "RemoveServices"; Flags: runhidden waituntilterminated

[Icons]
; 开始菜单
Name: "{group}\打开系统"; Filename: "{app}\scripts\open-web.bat"; IconFilename: "{app}\app\web\dist\favicon.ico"
Name: "{group}\启动服务"; Filename: "{app}\scripts\start-all.bat"
Name: "{group}\停止服务"; Filename: "{app}\scripts\stop-all.bat"
Name: "{group}\导入测试数据"; Filename: "{app}\scripts\seed-data.bat"
Name: "{group}\查看日志"; Filename: "{app}\logs"
Name: "{group}\编辑配置"; Filename: "notepad.exe"; Parameters: """{app}\app\.env"""
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"

; 桌面快捷方式
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\scripts\open-web.bat"; IconFilename: "{app}\app\web\dist\favicon.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："

[Code]
// ------------------------------------------------------------------
// 端口占用检查（安装前）
// ------------------------------------------------------------------
function IsPortInUse(Port: Integer): Boolean;
var
  ResultCode: Integer;
  TempFile: String;
begin
  TempFile := ExpandConstant('{tmp}\port_check.txt');
  Exec(ExpandConstant('{cmd}'), '/C netstat -an | findstr :' + IntToStr(Port) + ' | findstr LISTENING > "' + TempFile + '"',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := FileExists(TempFile) and (FileSize(TempFile) > 0);
end;

function InitializeSetup(): Boolean;
var
  BusyPorts: String;
begin
  BusyPorts := '';
  if IsPortInUse(5432) then BusyPorts := BusyPorts + '  5432 (PostgreSQL)' + #13#10;
  if IsPortInUse(4222) then BusyPorts := BusyPorts + '  4222 (NATS)' + #13#10;
  if IsPortInUse(8000) then BusyPorts := BusyPorts + '  8000 (Web)' + #13#10;
  if IsPortInUse(8001) then BusyPorts := BusyPorts + '  8001 (Gateway)' + #13#10;

  if BusyPorts <> '' then
  begin
    if MsgBox('检测到以下端口已被占用：' + #13#10 + #13#10 + BusyPorts +
              #13#10 + '安装可能失败或服务无法启动。是否继续？',
              mbConfirmation, MB_YESNO) <> IDYES then
    begin
      Result := False;
      Exit;
    end;
  end;

  Result := True;
end;

// ------------------------------------------------------------------
// 卸载前询问是否保留数据
// ------------------------------------------------------------------
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  KeepData: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    KeepData := MsgBox('是否保留业务数据库（postgresql\data 目录）？' + #13#10 +
                        '选择「是」将保留数据供下次安装使用。',
                        mbConfirmation, MB_YESNO);
    if KeepData = IDNO then
    begin
      DelTree(ExpandConstant('{app}\postgresql\data'), True, True, True);
      DelTree(ExpandConstant('{app}\nats\data'), True, True, True);
      DelTree(ExpandConstant('{app}\logs'), True, True, True);
    end;
  end;
end;
