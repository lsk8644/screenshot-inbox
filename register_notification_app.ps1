$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourcePath = Join-Path $projectRoot "windows\ShortcutRegistration.cs"
$launcherPath = Join-Path $projectRoot "launch_screenshot_inbox.ps1"
$powershellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$programsPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shortcutPath = Join-Path $programsPath "Screenshot Inbox.lnk"
$appId = "ScreenshotInbox.Local"

Add-Type -Path $sourcePath

$arguments = (
    '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
    $launcherPath +
    '"'
)
[ScreenshotInbox.Windows.ShortcutRegistration]::Create(
    $shortcutPath,
    $powershellPath,
    $arguments,
    $projectRoot,
    (Join-Path $env:SystemRoot "System32\imageres.dll"),
    15,
    $appId
)

$registryPath = "HKCU:\Software\Classes\AppUserModelId\$appId"
New-Item -Path $registryPath -Force | Out-Null
New-ItemProperty -Path $registryPath -Name "DisplayName" -Value "Screenshot Inbox" -PropertyType String -Force | Out-Null
New-ItemProperty -Path $registryPath -Name "ShowInSettings" -Value 1 -PropertyType DWord -Force | Out-Null
