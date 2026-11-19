<#
    Offline proof for Step 7 (AGENTS.md rule 6, steps/07-web-ui.md DoD).

    Blocks the project's own interpreter AND the Ollama binaries at Windows Firewall
    (inbound + outbound), proves the block with scripts\offline-check.py, then runs a
    five-question session against the local UI server - two of them follow-ups, so the
    condensation path runs too - and records what each answer came back as.

    Same method and the same reasons as scripts\offline-generation-proof.ps1 (read its
    header first; this reuses its firewall topology and its self-test):
      - loopback is deliberately not blocked: Windows Firewall does not filter it, and the
        local model is the runtime by design (D-029). What is proven is that no *external*
        network is used.
      - a venv's python.exe is a trampoline, so the base interpreter named in pyvenv.cfg is
        blocked as well; blocking only the trampoline blocked nothing (found 2026-11-17).
      - the rules are removed in a finally block and only the named programs are blocked.

    The server must already be running on 127.0.0.1:8000; this does not start it, because a
    server started under the rules would prove less than one that was already serving.

    Run from an elevated prompt:
        powershell -NoProfile -ExecutionPolicy Bypass -File scripts\offline-ui-proof.ps1

    Writes artifacts\step7\offline-ui.log, offline-ui-summary.txt, offline-ui-result.json.
#>

param(
    [string]$Server = 'http://127.0.0.1:8000'
)

$ErrorActionPreference = 'Stop'

$root   = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
$check  = Join-Path $PSScriptRoot 'offline-check.py'
$probe  = Join-Path $PSScriptRoot 'offline-ui-session.py'
$outDir = Join-Path $root 'artifacts\step7'
$log    = Join-Path $outDir 'offline-ui.log'
$summ   = Join-Path $outDir 'offline-ui-summary.txt'
$json   = Join-Path $outDir 'offline-ui-result.json'
$rule   = 'step7-offline-proof'

$basePython = $null
$pyvenv = Join-Path $root '.venv\pyvenv.cfg'
if (Test-Path -LiteralPath $pyvenv) {
    $venvHome = Get-Content -LiteralPath $pyvenv | Where-Object { $_ -match '^home\s*=' } | Select-Object -First 1
    if ($venvHome) { $basePython = Join-Path (($venvHome -replace '^home\s*=\s*', '').Trim()) 'python.exe' }
}
$programs = @($python, $ollama)
if ($basePython -and (Test-Path -LiteralPath $basePython)) { $programs += $basePython }

foreach ($path in @($python, $ollama, $check, $probe)) {
    if (-not (Test-Path -LiteralPath $path)) { throw ("missing: " + $path) }
}

# The server has to be answering before the block goes up, or a failure would be about a
# dead port rather than about the network.
try {
    $health = Invoke-RestMethod -Uri ($Server + '/api/health') -TimeoutSec 10
} catch {
    throw ("UI server is not answering on " + $Server + "; start it first. " + $_.Exception.Message)
}
if (-not $health.ok) { throw ("UI server reports not ok: " + ($health | ConvertTo-Json -Compress)) }

New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$env:HF_HUB_OFFLINE       = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE  = '1'

function Write-TextNoBom {
    param([string]$Path, [string]$Text)
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text + "`n", $encoding)
}

function Invoke-Blocked {
    param([string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $lines = @(& $python @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        return @{ exit = $LASTEXITCODE; output = $lines }
    } finally {
        $ErrorActionPreference = $previous
    }
}

$lines = @()
$started = Get-Date
$blockExit = $null
$sessionExit = $null
$active = 0
$left = 0
try {
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    foreach ($program in $programs) {
        New-NetFirewallRule -DisplayName $rule -Direction Outbound -Program $program -Action Block -Profile Any | Out-Null
        New-NetFirewallRule -DisplayName $rule -Direction Inbound  -Program $program -Action Block -Profile Any | Out-Null
    }
    $active = (Get-NetFirewallRule -DisplayName $rule | Measure-Object).Count
    $lines += ("firewall rules active during test: " + $active + " (" + ($programs.Count * 2) + " = inbound + outbound for " + $programs.Count + " programs)")
    $lines += ("blocked programs: " + ($programs -join ' ; '))
    $lines += ("server: " + $Server + " (model " + $health.model + ", " + $health.documents + " documents)")
    $lines += ("started: " + $started.ToString('s'))

    $checkRun = Invoke-Blocked -Arguments @($check)
    $blockExit = $checkRun.exit
    $lines += $checkRun.output
    $lines += ("offline-check exit code: " + $blockExit + " (0 = every external connection was refused)")

    if ($blockExit -eq 0) {
        $session = Invoke-Blocked -Arguments @($probe, $Server)
        $sessionExit = $session.exit
        $lines += $session.output
        $lines += ("ui session exit code: " + $sessionExit)
    } else {
        $lines += 'ui session skipped: the firewall block is not effective for this interpreter'
    }
} finally {
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    $left = (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue | Measure-Object).Count
    $lines += ("firewall rules left after the run: " + $left + " (0 = cleaned up)")
    $lines += ("finished: " + (Get-Date).ToString('s'))
    Write-TextNoBom -Path $log -Text ($lines -join "`n")
}

$verdict = if ($blockExit -eq 0 -and $sessionExit -eq 0 -and $left -eq 0) { 'PASS' } else { 'FAIL' }
$summary = @()
$summary += ("offline ui run: " + $verdict)
$summary += ("rules active during the run: " + $active + ", left after: " + $left)
$summary += ("blocked programs: " + ($programs -join ' ; '))
$summary += ("block self-test (offline-check.py): exit " + $blockExit + " (0 = network refused)")
$summary += ("5-question ui session exit: " + $sessionExit)
$summary += ("log: " + $log)
Write-TextNoBom -Path $summ -Text ($summary -join "`n")

[ordered]@{
    verdict = $verdict
    rules_active = $active
    rules_left = $left
    programs = $programs
    block_check_exit = $blockExit
    session_exit = $sessionExit
    server = $Server
    log = $log
} | ConvertTo-Json -Depth 5 | ForEach-Object { Write-TextNoBom -Path $json -Text $_ }

$summary | ForEach-Object { Write-Host $_ }
if ($verdict -ne 'PASS') { exit 1 }
