# Start the local model server through Ollama (offline, localhost only).
#
# Usage:
#   .\scripts\launch-llm.ps1                    # qwen3.5:4b on 127.0.0.1:11434
#   .\scripts\launch-llm.ps1 -Model qwen2.5 -KeepAlive 30m
#
# The default model is qwen3.5:4b, which won the Step 2 comparison (D-047) at
# 23/30 oracle against 18/30 for the 7B, and is faster on every latency measure.
# Thinking is sent as false: with it on, qwen3.5 returns empty answers.
#
# Ollama replaced the pinned llama.cpp build on 2026-11-13 (owner's decision).
# It was measured faster on the same weights: 499 tok/s prompt and 9.43 tok/s
# generation, against 293 and 7.46 for llama-server.
#
# Offline settings are exported here, not in the caller's shell, so every launch
# is offline regardless of how the session started. Nothing here reaches the
# network: Ollama serves from its local model store and binds to localhost.

param(
    [string]$Model     = "qwen3.5:4b",
    [int]   $Port      = 11434,
    [string]$KeepAlive = "30m",
    [switch]$Think
)

$ErrorActionPreference = "Stop"

# --- offline mode (D-026) ---
$env:HF_HUB_OFFLINE       = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_DATASETS_OFFLINE  = "1"

# localhost only: never bind to 0.0.0.0
$env:OLLAMA_HOST = "127.0.0.1:$Port"

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    throw "ollama not found on PATH. Install it, then run: ollama pull $Model"
}

# Join first: -notmatch against an array returns every line that does NOT match,
# so the header row alone would make this throw even when the model is present.
$installed = ((& ollama list) 2>&1) -join "`n"
if ($installed -notmatch [regex]::Escape($Model)) {
    throw "Model '$Model' is not in the local Ollama store. Run: ollama pull $Model"
}

Write-Host "offline mode : HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1"
Write-Host "model        : $Model (thinking $(if ($Think) { 'ON' } else { 'off' }))"
Write-Host "listen       : http://127.0.0.1:$Port"

# Load the model now so the first question does not pay the load time.
# Uses the HTTP API, not `ollama run`: an empty prompt there drops into an
# interactive REPL that waits for input forever.
$warm = @{ model = $Model; prompt = ""; keep_alive = $KeepAlive; think = [bool]$Think } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/generate" -Method Post `
    -Body $warm -ContentType "application/json" -TimeoutSec 300 | Out-Null

$ps = ((& ollama ps) 2>&1) -join "`n"
Write-Host "loaded       :"
$ps -split "`n" | Where-Object { $_ -match [regex]::Escape($Model) -or $_ -match "^NAME" } | ForEach-Object { Write-Host "  $_" }

# These are API endpoints for programs, not pages. A browser always sends GET,
# and Ollama answers GET on a POST-only route with 405 Method Not Allowed - so
# printing a bare URL here invites someone to click it and report a fault. They
# are labelled POST, and the one address that does answer GET is listed too.
Write-Host "api          : POST http://127.0.0.1:$Port/api/chat"
Write-Host "               POST http://127.0.0.1:$Port/v1/chat/completions"
Write-Host "               POST only - opening these in a browser sends GET and shows"
Write-Host "               405 Method Not Allowed. That is correct behaviour, not a fault."
Write-Host "status       : http://127.0.0.1:$Port   (this one answers GET: 'Ollama is running')"

# --- chat UI link ---
# The model server and the chat UI are separate processes. This prints the URL
# either way, and says plainly whether it will answer right now, so nobody opens
# a link that only looks like it works (a dead port 8000 is what produced a 405
# in the browser once: the request was answered by a static handler, not the app).
$UiPort = if ($env:UI_PORT) { [int]$env:UI_PORT } else { 8000 }
$UiUrl  = "http://127.0.0.1:$UiPort"
try {
    Invoke-RestMethod -Uri "$UiUrl/api/health" -TimeoutSec 3 | Out-Null
    Write-Host "chat         : $UiUrl   (running - open it)"
    Write-Host "               health: $UiUrl/api/health"
} catch {
    Write-Host "chat         : $UiUrl   (not running yet)"
    Write-Host "               start it: .\scripts\open-chat.ps1 -Start"
    Write-Host "               or      : .venv\Scripts\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port $UiPort"
}

Write-Host "stop         : ollama stop $Model"
