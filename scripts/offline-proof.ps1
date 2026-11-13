# Offline proof for Step 0 (AGENTS.md rule 6, D-026).
#
# Blocks llama-server.exe at Windows Firewall (inbound + outbound), then starts
# the server and runs a prompt. If the answer still comes back, the binary needs
# no network. The rule is removed in a finally block, so it never outlives a run.
#
# Run elevated (it creates and deletes firewall rules):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\offline-proof.ps1
#
# Writes artifacts/step0/offline-run.log, offline-completion.json, offline-summary.txt

param([int]$Port = 8080)

$ErrorActionPreference = "Stop"
$root    = Split-Path -Parent $PSScriptRoot
$exe     = Join-Path $root "tools\llama.cpp\llama-server.exe"
$model   = Join-Path $root "models\qwen2.5-1.5b-instruct-q4_k_m.gguf"
$log     = Join-Path $root "artifacts\step0\offline-run.log"
$stdout  = Join-Path $root "artifacts\step0\offline-run.out.log"
$json    = Join-Path $root "artifacts\step0\offline-completion.json"
$summary = Join-Path $root "artifacts\step0\offline-summary.txt"
$rule    = "step0-offline-proof-llama"

foreach ($p in @($exe, $model)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "Missing: $p" }
}

$env:HF_HUB_OFFLINE       = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_DATASETS_OFFLINE  = "1"

$lines = @()
$proc  = $null
try {
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $rule -Direction Outbound -Program $exe -Action Block -Profile Any | Out-Null
    New-NetFirewallRule -DisplayName $rule -Direction Inbound  -Program $exe -Action Block -Profile Any | Out-Null
    $active = (Get-NetFirewallRule -DisplayName $rule | Measure-Object).Count
    $lines += "firewall rules active during test: $active (2 = inbound + outbound block)"

    $proc = Start-Process -FilePath $exe -PassThru -WindowStyle Hidden -ArgumentList @(
        '--model', $model, '--host', '127.0.0.1', '--port', "$Port",
        '--ctx-size', '4096', '--n-gpu-layers', '99', '--threads', '8', '-lv', '5'
    ) -RedirectStandardOutput $stdout -RedirectStandardError $log
    $lines += "server pid: $($proc.Id)"

    $ready = $false
    for ($i = 0; $i -lt 120; $i++) {
        try {
            $r = Invoke-WebRequest "http://127.0.0.1:$Port/health" -TimeoutSec 2 -UseBasicParsing
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 1
    }
    $lines += "health ready with network blocked: $ready"

    if ($ready) {
        $body = @{
            prompt      = "In one sentence, what is the capital of Nepal, and name the two rivers it sits on."
            n_predict   = 64
            temperature = 0
        } | ConvertTo-Json
        $resp = Invoke-RestMethod "http://127.0.0.1:$Port/completion" -Method Post `
                    -ContentType "application/json" -Body $body -TimeoutSec 180
        $resp | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $json -Encoding UTF8
        $lines += "completion returned: $(($resp.timings.predicted_n)) tokens at $([math]::Round($resp.timings.predicted_per_second,1)) tok/s"
        $lines += "answer: $($resp.content -replace '\s+', ' ')"
    }

    $lines += "vram used during run: $(& nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
}
finally {
    if ($proc) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    $left = (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue | Measure-Object).Count
    $lines += "firewall rules removed (remaining: $left)"
    $lines += "offline run: $(if ($ready) { 'PASS' } else { 'FAIL' })"
    $lines | Set-Content -LiteralPath $summary -Encoding UTF8
    $lines
}
