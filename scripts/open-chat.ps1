# Open the chat UI.
#
# Usage:
#   .\scripts\open-chat.ps1              # print the link and open it (server must be running)
#   .\scripts\open-chat.ps1 -NoBrowser   # print the link only
#   .\scripts\open-chat.ps1 -Start       # run the server in this window, then open the link
#   .\scripts\open-chat.ps1 -Start -Port 8001
#   $env:UI_PORT = 8300; .\scripts\open-chat.ps1 -Start   # pin the port
#
# The port is measured before anything starts. Windows reserves long port ranges
# for Hyper-V/WinNAT (`netsh interface ipv4 show excludedportrange protocol=tcp`),
# and a bind inside one fails with WinError 10013 while nothing is listening. A
# reserved port is replaced by a free one in 8300-8599, and the swap is printed.
#   $env:UI_PORT = 8300; .\scripts\open-chat.ps1 -Start   # pin the port
#
# The port is measured first. If Windows has reserved it (Hyper-V/WinNAT take
# long port ranges; a bind inside one fails with WinError 10013 while nothing is
# listening), a free port in 8300-8599 is used and printed instead.
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

# --- port -------------------------------------------------------------------
# -Port wins, then UI_PORT, then the default 8000. A requested port can be
# unbindable for a reason that has nothing to do with this app: Windows hands
# long stretches of ports to Hyper-V/WinNAT (`netsh interface ipv4 show
# excludedportrange protocol=tcp`), and binding inside one fails with WinError
# 10013 while nothing is listening. So the port is measured before the server is
# started, and a reserved one is replaced by a free port that is printed, never
# swapped silently.
if (-not $PSBoundParameters.ContainsKey('Port') -and $env:UI_PORT) {
    $Port = [int]$env:UI_PORT
}

function Test-ChatPort([int]$Candidate) {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:$Candidate/api/health" -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Test-PortBindable([int]$Candidate) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Candidate)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { try { $listener.Stop() } catch { } }
    }
}

# A refused connection answers at once; a filtered one is cut off here, so the scan
# stays short even when Windows swallows the SYN.
function Test-PortOpen([int]$Candidate) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $client.ConnectAsync([System.Net.IPAddress]::Loopback, $Candidate).Wait(150) | Out-Null
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

if (-not (Test-ChatPort $Port) -and -not (Test-PortBindable $Port)) {
    # Take the first port that is either an already-running chat server or free to
    # bind, so a second -Start reports the running server instead of starting a
    # duplicate on a higher port.
    $candidate = $null
    foreach ($p in 8300..8599) {
        if (Test-PortOpen $p) {
            if (Test-ChatPort $p) { $candidate = $p }
        } elseif (Test-PortBindable $p) {
            $candidate = $p
        }
        if ($candidate) { break }
    }
    if (-not $candidate) {
        throw "No usable port: $Port is reserved by Windows and 8300-8599 are taken or reserved too. Set `$env:UI_PORT to a free port."
    }
    Write-Host "chat   : 127.0.0.1:$Port is reserved by Windows (Hyper-V/WinNAT), so using $candidate"
    Write-Host "         pin it with: `$env:UI_PORT = $candidate"
    $Port = $candidate
}

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
        Write-Host "ollama :"
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
            Write-Host "         model server is up"
        } catch {
            Write-Host "         model server is NOT up - run .\scripts\launch-llm.ps1 first"
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
