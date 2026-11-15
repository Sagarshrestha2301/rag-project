# Open the chat UI.
#
# Usage:
#   .\scripts\open-chat.ps1              # print the link and open it (server must be running)
#   .\scripts\open-chat.ps1 -NoBrowser   # print the link only
#   .\scripts\open-chat.ps1 -Start       # run the server in this window, then open the link
#   .\scripts\open-chat.ps1 -Start -Port 8001
#
# The chat UI is a separate process from Ollama (scripts\launch-llm.ps1).
# -Start runs uvicorn in the foreground on purpose: a server started in the
# background by a script inherits the caller's console handles, which made a
# cold start that had already succeeded block its caller for 180 s. In the
# foreground you see the request log and Ctrl+C stops it, which is the usual
# way to run a dev server.
#
# Nothing here downloads anything; it only runs local code already in the repo.

param(
    [int]    $Port = 8000,
    [switch] $NoBrowser,
    [switch] $Start,
    [string] $Python = ".venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$url    = "http://127.0.0.1:$Port"
$health = "$url/api/health"

function Test-Chat {
    try {
        Invoke-RestMethod -Uri $health -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-Chat)) {
    if (-not (Test-Path $Python)) {
        throw "$Python not found. Run this from the project root, or pass -Python."
    }
    if (-not $Start) {
        Write-Host "chat   : not running at $url"
        Write-Host "         start it with: .\scripts\open-chat.ps1 -Start   (Ctrl+C to stop)"
        Write-Host "         or            : $Python -m uvicorn ui.server:app --host 127.0.0.1 --port $Port"
        if (-not (Test-Chat -ErrorAction SilentlyContinue)) {
            Write-Host "ollama :"
            try {
                Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
                Write-Host "         model server is up"
            } catch {
                Write-Host "         model server is NOT up - run .\scripts\launch-llm.ps1 first"
            }
        }
        exit 1
    }
    Write-Host "chat   : starting on 127.0.0.1:$Port - open $url once it says 'Application startup complete'"
    Write-Host "         Ctrl+C stops it"
    if (-not $NoBrowser) {
        Start-Process $url
    }
    & $Python -m uvicorn ui.server:app --host 127.0.0.1 --port $Port
    exit $LASTEXITCODE
}

$state = Invoke-RestMethod -Uri $health -TimeoutSec 3
Write-Host "chat   : running at $url"
Write-Host "model  : $($state.model)  (loaded: $($state.loaded))"
Write-Host "index  : $($state.pages) pages, $($state.documents) documents"
if (-not $NoBrowser) {
    Start-Process $url
}
