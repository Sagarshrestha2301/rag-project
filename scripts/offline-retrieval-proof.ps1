<#
    Offline proof for Step 5 (AGENTS.md rule 6, D-026).

    Blocks the project's own interpreter at Windows Firewall (inbound + outbound), then
    runs the retrieval eval with it. Retrieval reads chunks, the page index, LanceDB and
    the bge model from disk; if any of it reached for the network, the blocked process
    could not finish. The rules are removed in a finally block, so they never outlive a
    run, and only `.venv\Scripts\python.exe` is blocked - not the whole machine.

    Run it from an elevated prompt (it creates and deletes firewall rules):
        powershell -NoProfile -ExecutionPolicy Bypass -File scripts\offline-retrieval-proof.ps1

    Writes artifacts\step5\offline-run.log, offline-summary.txt and offline-result.json.
#>

param(
    [string]$Label = 'offline-step5',
    [int]$Port = 0
)

$ErrorActionPreference = 'Stop'

$root   = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$outDir = Join-Path $root 'artifacts\step5'
$log    = Join-Path $outDir 'offline-run.log'
$summ   = Join-Path $outDir 'offline-summary.txt'
$json   = Join-Path $outDir 'offline-result.json'
$rule   = 'step5-offline-proof-python'
$runDir = Join-Path $root ('eval\runs\' + (Get-Date).ToString('yyyy-MM-dd') + '-' + $Label)

if (-not (Test-Path -LiteralPath $python)) { throw ("missing interpreter: " + $python) }
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

# Same offline settings the launch scripts set. These are a request; the firewall rule
# is the enforcement, which is why the rule count is recorded during the run.
$env:HF_HUB_OFFLINE       = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE  = '1'

$lines = @()
$started = Get-Date
$exitCode = $null
try {
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $rule -Direction Outbound -Program $python -Action Block -Profile Any | Out-Null
    New-NetFirewallRule -DisplayName $rule -Direction Inbound  -Program $python -Action Block -Profile Any | Out-Null
    $active = (Get-NetFirewallRule -DisplayName $rule | Measure-Object).Count
    $lines += ("firewall rules active during test: " + $active + " (2 = inbound + outbound block)")
    $lines += ("blocked program: " + $python)
    $lines += ("started: " + $started.ToString('s'))

    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = @(& $python (Join-Path $root 'eval\run_retrieval.py') '--label' $Label 2>&1 |
                    ForEach-Object { $_.ToString() })
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    $lines += $output
    $lines += ("exit code: " + $exitCode)
} finally {
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    $left = (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue | Measure-Object).Count
    $lines += ("firewall rules left after the run: " + $left + " (0 = cleaned up)")
    $lines += ("finished: " + (Get-Date).ToString('s'))
    $lines | Set-Content -LiteralPath $log -Encoding UTF8
}

$scoresPath = Join-Path $runDir 'scores.json'
$scores = if (Test-Path -LiteralPath $scoresPath) {
    Get-Content -LiteralPath $scoresPath -Raw | ConvertFrom-Json
} else { $null }

$verdict = if ($exitCode -eq 0 -and $scores) { 'PASS' } else { 'FAIL' }
$summary = @()
$summary += ("offline run: " + $verdict)
$summary += ("label: " + $Label)
$summary += ("rules active during the run: 2, left after: " + $left)
$summary += ("exit code: " + $exitCode)
if ($scores) {
    $summary += ("recall@5: " + $scores.retrieval.'recall@5'.pass.count + "/" + $scores.retrieval.'recall@5'.pass.of)
    $summary += ("recall@10: " + $scores.retrieval.'recall@10'.pass.count + "/" + $scores.retrieval.'recall@10'.pass.of)
    $summary += ("MRR: " + $scores.mrr)
}
$summary += ("log: " + $log)
$summary | Set-Content -LiteralPath $summ -Encoding UTF8

[ordered]@{
    verdict = $verdict
    label = $Label
    rules_active = 2
    rules_left = $left
    exit_code = $exitCode
    recall_at_5 = if ($scores) { $scores.retrieval.'recall@5'.pass } else { $null }
    recall_at_10 = if ($scores) { $scores.retrieval.'recall@10'.pass } else { $null }
    mrr = if ($scores) { $scores.mrr } else { $null }
    run = $runDir
    log = $log
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $json -Encoding UTF8

$summary | ForEach-Object { Write-Host $_ }
if ($verdict -ne 'PASS') { exit 1 }
