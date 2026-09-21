$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appUrl = "http://127.0.0.1:8765/"
$healthUrl = "http://127.0.0.1:8765/api/health"
$notificationRegistration = Join-Path $projectRoot "register_notification_app.ps1"

if (Test-Path -LiteralPath $notificationRegistration) {
    & $notificationRegistration
}

function Test-ScreenshotInbox {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        return $health.status -eq "ok"
    }
    catch {
        return $false
    }
}

if (-not (Test-ScreenshotInbox)) {
    $launcher = Get-Command screenshot-inbox -ErrorAction SilentlyContinue
    if (-not $launcher) {
        $fallback = Join-Path $env:LOCALAPPDATA `
            "Programs\Python\Python313\Scripts\screenshot-inbox.exe"
        if (Test-Path -LiteralPath $fallback) {
            $launcher = Get-Item -LiteralPath $fallback
        }
    }
    if (-not $launcher) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "Screenshot Inbox 실행 파일을 찾을 수 없습니다.",
            "Screenshot Inbox"
        ) | Out-Null
        exit 1
    }

    $workDirectory = Join-Path $projectRoot "work"
    New-Item -ItemType Directory -Path $workDirectory -Force | Out-Null
    Start-Process `
        -FilePath $launcher.Source `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $workDirectory "desktop-launch.stdout.log") `
        -RedirectStandardError (Join-Path $workDirectory "desktop-launch.stderr.log")

    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        if (Test-ScreenshotInbox) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "Screenshot Inbox을 시작하지 못했습니다. work 폴더의 로그를 확인하세요.",
            "Screenshot Inbox"
        ) | Out-Null
        exit 1
    }
}

$appBrowserCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe")
)
$appBrowser = $appBrowserCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    Select-Object -First 1

if ($appBrowser) {
    Start-Process -FilePath $appBrowser -ArgumentList "--app=$appUrl"
}
else {
    Start-Process $appUrl
}
