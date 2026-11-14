# Start the local model server through Ollama (offline, localhost only).
#
# Usage:
#   .\scripts\launch-llm.ps1                    # qwen2.5 on 127.0.0.1:11434
#   .\scripts\launch-llm.ps1 -Model qwen2.5 -KeepAlive 30m
#
# Ollama replaced the pinned llama.cpp build on 2026-11-13 (owner's decision).
# It was measured faster on the same weights: 499 tok/s prompt and 9.43 tok/s
# generation, against 293 and 7.46 for llama-server.
#
# Offline settings are exported here, not in the caller's shell, so every launch
# is offline regardless of how the session started. Nothing here reaches the
# network: Ollama serves from its local model store and binds to localhost.

param(
    [string]$Model     = "qwen2.5",
    [int]   $Port      = 11434,
    [string]$KeepAlive = "30m"
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

$installed = (& ollama list) 2>&1
if ($installed -notmatch [regex]::Escape($Model)) {
    throw "Model '$Model' is not in the local Ollama store. Run: ollama pull $Model"
}

Write-Host "offline mode : HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1"
Write-Host "model        : $Model"
Write-Host "listen       : http://127.0.0.1:$Port"

# Load the model now so the first question does not pay the load time.
& ollama run $Model --keepalive $KeepAlive "" | Out-Null

Write-Host "ready        : POST http://127.0.0.1:$Port/api/chat"
Write-Host "               POST http://127.0.0.1:$Port/v1/chat/completions (OpenAI-compatible)"
