# Start the local llama.cpp server in offline mode (D-026).
#
# Usage:
#   .\scripts\launch-llm.ps1                                   # defaults below
#   .\scripts\launch-llm.ps1 -Model models\other-model.gguf -Port 8090
#
# Offline settings are exported here, not in the caller's shell, so every launch
# is offline regardless of how the session started. Nothing in this script
# reaches the network: the binary, the model and the HTTP bind are all local.

param(
    [string]$Model     = "models\qwen2.5-1.5b-instruct-q4_k_m.gguf",
    [int]   $Port      = 8080,
    [int]   $Ctx       = 4096,
    [int]   $GpuLayers = 99
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# --- offline mode (D-026) ---
$env:HF_HUB_OFFLINE       = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_DATASETS_OFFLINE  = "1"
$env:HF_HOME              = Join-Path $root "models\hf"

$server    = Join-Path $root "tools\llama.cpp\llama-server.exe"
$modelPath = Join-Path $root $Model

foreach ($path in @($server, $modelPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file missing: $path (see 'Pinned tools and downloaded files' in STATUS.md)"
    }
}

Write-Host "offline mode : HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1"
Write-Host "model        : $modelPath"
Write-Host "listen       : http://127.0.0.1:$Port"

& $server --model $modelPath --host 127.0.0.1 --port $Port --ctx-size $Ctx --n-gpu-layers $GpuLayers
