$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$healthUrl = "http://127.0.0.1:8765/api/health"

try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.status -eq "ok") {
        exit 0
    }
}
catch {
    # The local server is not running yet.
}

$launcher = Get-Command screenshot-inbox -ErrorAction SilentlyContinue
if (-not $launcher) {
    $fallback = Join-Path $env:LOCALAPPDATA `
        "Programs\Python\Python313\Scripts\screenshot-inbox.exe"
    if (Test-Path -LiteralPath $fallback) {
        $launcher = Get-Item -LiteralPath $fallback
    }
}
if (-not $launcher) {
    exit 1
}

$workDirectory = Join-Path $projectRoot "work"
New-Item -ItemType Directory -Path $workDirectory -Force | Out-Null
Start-Process `
    -FilePath $launcher.Source `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $workDirectory "background.stdout.log") `
    -RedirectStandardError (Join-Path $workDirectory "background.stderr.log")
