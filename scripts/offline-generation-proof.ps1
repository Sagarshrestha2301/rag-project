<#
    Offline proof for Step 6 (AGENTS.md rule 6, D-026).

    Blocks the project's own interpreter AND the Ollama binaries at Windows Firewall
    (inbound + outbound), then runs the full generation eval - router, retrieval, prompt,
    Ollama on 127.0.0.1, quote verification - and scores it. Everything the run needs
    (corpus PDFs, page index, model blobs, prompt) is read from disk or from localhost; if
    any of it reached for the network, the blocked process could not finish.

    Loopback is deliberately not blocked: Windows Firewall does not filter it, and the
    local model is the runtime by design (D-029). What this proves is that no *external*
    network is used.

    A Windows venv's .venv\Scripts\python.exe is a trampoline: it starts the base
    interpreter named in pyvenv.cfg, and that child is what opens sockets. Blocking only
    the trampoline blocked nothing - found on 2026-11-17, when a probe from the "blocked"
    interpreter still reached 1.1.1.1:443 while four rules were active. Both interpreter
    paths are now blocked, and the script proves its own block before spending the eval:
    scripts\offline-check.py runs under the rules and the eval only starts if every
    external connection fails. A run that cannot block the network reports FAIL.

    The rules are removed in a finally block, so they never outlive a run, and only the
    named programs are blocked - not the whole machine.

    Run it from an elevated prompt (it creates and deletes firewall rules):
        powershell -NoProfile -ExecutionPolicy Bypass -File scripts\offline-generation-proof.ps1
        powershell -NoProfile -ExecutionPolicy Bypass -File scripts\offline-generation-proof.ps1 -Label offline-step6 -Model 'qwen3.5:4b'

    Writes artifacts\step6\offline-run.log, offline-summary.txt and offline-result.json.
#>

param(
    [string]$Label = 'offline-step6',
    [string]$Model = 'qwen3.5:4b'
)

$ErrorActionPreference = 'Stop'

$root   = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
$check  = Join-Path $PSScriptRoot 'offline-check.py'

# The interpreter that actually opens sockets: .venv\Scripts\python.exe starts this one
# (pyvenv.cfg `home`), so the firewall has to block the base image too.
$basePython = $null
$pyvenv = Join-Path $root '.venv\pyvenv.cfg'
if (Test-Path -LiteralPath $pyvenv) {
    # $HOME is a read-only PowerShell automatic variable, hence $venvHome.
    $venvHome = Get-Content -LiteralPath $pyvenv | Where-Object { $_ -match '^home\s*=' } | Select-Object -First 1
    if ($venvHome) { $basePython = Join-Path (($venvHome -replace '^home\s*=\s*', '').Trim()) 'python.exe' }
}
$programs = @($python, $ollama)
if ($basePython -and (Test-Path -LiteralPath $basePython)) { $programs += $basePython }
$outDir = Join-Path $root 'artifacts\step6'
$log    = Join-Path $outDir 'offline-run.log'
$summ   = Join-Path $outDir 'offline-summary.txt'
$json   = Join-Path $outDir 'offline-result.json'
$rule   = 'step6-offline-proof'
$runDir = Join-Path $root ('eval\runs\' + (Get-Date).ToString('yyyy-MM-dd') + '-' + $Label)

if (-not (Test-Path -LiteralPath $python)) { throw ("missing interpreter: " + $python) }
if (-not (Test-Path -LiteralPath $ollama)) { throw ("missing Ollama binary: " + $ollama) }
if (-not (Test-Path -LiteralPath $check)) { throw ("missing block probe: " + $check) }

# The model must already be served locally, or the blocked run would fail for the wrong
# reason (an unreachable server, not a network call).
$tags = $null
try { $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10 } catch {
    throw ("Ollama is not answering on 127.0.0.1:11434; start it with 'ollama serve' first. " + $_.Exception.Message)
}
if (-not ($tags.models | Where-Object { $_.name -eq $Model })) {
    throw ("model not pulled: " + $Model + " (have: " + (($tags.models | ForEach-Object { $_.name }) -join ', ') + ")")
}

New-Item -ItemType Directory -Path $outDir -Force | Out-Null

# Same offline settings the launch scripts set. These are a request; the firewall rule
# is the enforcement, which is why the rule count is recorded during the run.
$env:HF_HUB_OFFLINE       = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE  = '1'

function Write-TextNoBom {
    # PowerShell 5.1's Set-Content -Encoding UTF8 writes a BOM, which makes the JSON
    # artifact unreadable to json.load(); this writes the bytes it means to write.
    param([string]$Path, [string]$Text)
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text + "`n", $encoding)
}

function Invoke-Blocked {
    # Runs a command while the firewall rules are active and returns exit code + output.
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
$evalExit = $null
$scoreExit = $null
$blockCheckExit = $null
$active = 0
try {
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    foreach ($program in $programs) {
        New-NetFirewallRule -DisplayName $rule -Direction Outbound -Program $program -Action Block -Profile Any | Out-Null
        New-NetFirewallRule -DisplayName $rule -Direction Inbound  -Program $program -Action Block -Profile Any | Out-Null
    }
    $active = (Get-NetFirewallRule -DisplayName $rule | Measure-Object).Count
    $lines += ("firewall rules active during test: " + $active + " (" + ($programs.Count * 2) + " = inbound + outbound for " + $programs.Count + " programs)")
    $lines += ("blocked programs: " + ($programs -join ' ; '))
    $lines += ("model: " + $Model + " (digest " + ($tags.models | Where-Object { $_.name -eq $Model }).digest + ")")
    $lines += ("started: " + $started.ToString('s'))

    # Prove the block before spending twenty minutes on an eval that would prove nothing.
    $checkRun = Invoke-Blocked -Arguments @($check)
    $blockCheckExit = $checkRun.exit
    $lines += $checkRun.output
    $lines += ("offline-check exit code: " + $blockCheckExit + " (0 = every external connection was refused)")

    if ($blockCheckExit -eq 0) {
        $eval = Invoke-Blocked -Arguments @(
            (Join-Path $root 'eval\run_generation.py'), '--label', $Label, '--model', $Model)
        $evalExit = $eval.exit
        $lines += $eval.output
        $lines += ("generation eval exit code: " + $evalExit)

        $runFile = Join-Path $runDir 'run.jsonl'
        if (Test-Path -LiteralPath $runFile) {
            $score = Invoke-Blocked -Arguments @(
                (Join-Path $root 'eval\score.py'), '--run', $runFile, '--out', $runDir, '--label', $Label)
            $scoreExit = $score.exit
            $lines += $score.output
            $lines += ("score exit code: " + $scoreExit)
        } else {
            $lines += ("no run.jsonl written: " + $runFile)
        }
    } else {
        $lines += 'eval skipped: the firewall block is not effective for this interpreter'
    }
} finally {
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    $left = (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue | Measure-Object).Count
    $lines += ("firewall rules left after the run: " + $left + " (0 = cleaned up)")
    $lines += ("finished: " + (Get-Date).ToString('s'))
    Write-TextNoBom -Path $log -Text ($lines -join "`n")
}

$scoresPath = Join-Path $runDir 'scores.json'
$scores = if (Test-Path -LiteralPath $scoresPath) {
    Get-Content -LiteralPath $scoresPath -Raw | ConvertFrom-Json
} else { $null }

$verdict = if ($blockCheckExit -eq 0 -and $evalExit -eq 0 -and $scoreExit -eq 0 -and $scores) { 'PASS' } else { 'FAIL' }
$summary = @()
$summary += ("offline run: " + $verdict)
$summary += ("label: " + $Label)
$summary += ("rules active during the run: " + $active + ", left after: " + $left)
$summary += ("blocked programs: " + ($programs -join ' ; '))
$summary += ("block self-test (offline-check.py): exit " + $blockCheckExit + " (0 = network refused)")
$summary += ("generation eval exit: " + $evalExit + ", score exit: " + $scoreExit)
if ($scores) {
    $summary += ("citation: " + $scores.summary.citation.count + "/" + $scores.summary.citation.of)
    $summary += ("numeric: " + $scores.summary.numeric.count + "/" + $scores.summary.numeric.of)
    $summary += ("not-found (a): " + $scores.summary.notfound_a.count + "/" + $scores.summary.notfound_a.of)
    $summary += ("passed: " + $scores.summary.passed.count + "/" + $scores.summary.passed.of)
}
$summary += ("log: " + $log)
Write-TextNoBom -Path $summ -Text ($summary -join "`n")

[ordered]@{
    verdict = $verdict
    label = $Label
    model = $Model
    rules_active = $active
    rules_left = $left
    programs = $programs
    block_check_exit = $blockCheckExit
    eval_exit = $evalExit
    score_exit = $scoreExit
    citation = if ($scores) { $scores.summary.citation } else { $null }
    numeric = if ($scores) { $scores.summary.numeric } else { $null }
    notfound_a = if ($scores) { $scores.summary.notfound_a } else { $null }
    passed = if ($scores) { $scores.summary.passed } else { $null }
    run = $runDir
    log = $log
} | ConvertTo-Json -Depth 5 | ForEach-Object { Write-TextNoBom -Path $json -Text $_ }

$summary | ForEach-Object { Write-Host $_ }
if ($verdict -ne 'PASS') { exit 1 }
