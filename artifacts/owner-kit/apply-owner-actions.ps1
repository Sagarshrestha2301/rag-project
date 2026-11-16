<#
    apply-owner-actions.ps1  -  OWNER ONLY. An agent must never run or edit this file.

    Purpose: bring APPROVALS.md, the git tags and DECISIONS.md up to date in one
    reviewable run, instead of leaving the record behind what actually happened.

    What it does, in order:
      1. refuses to run if the working tree is not clean, or if any decision
         variable below is still 'PENDING';
      2. adds the missing approval lines to APPROVALS.md and commits them: completion
          for steps 01 and 02, start for steps 02, 03, 04 and 05;
      3. creates step-00-approved and step-01-approved (step 02 only if you say so);
      4. adds APPROVED lines to D-038, D-040, D-042, D-043, D-044 and a SUPERSEDED
         line to D-039 in DECISIONS.md, and commits them;
      5. prints the two verification commands from APPROVALS.md.

    Before running, set each decision variable below to 'APPROVE' or 'REJECT' after
    reading that decision in DECISIONS.md. PENDING means "I have not decided yet",
    and the script will not act on a decision you have not made.

    Dry run (changes nothing, prints what it would do):
        powershell -NoProfile -ExecutionPolicy Bypass -File artifacts\owner-kit\apply-owner-actions.ps1 -WhatIf

    Real run:
        powershell -NoProfile -ExecutionPolicy Bypass -File artifacts\owner-kit\apply-owner-actions.ps1
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Your decisions. Change 'PENDING' to 'APPROVE' or 'REJECT'. Nothing else here.
# Evidence for each one is in OWNER-CHECKLIST.md next to this file.
# ---------------------------------------------------------------------------
$D038 = 'PENDING'   # D-038 staged corpus growth (one document, then 30-50, then all)
$D040 = 'PENDING'   # D-040 generator is your existing qwen2.5 7B, fallback 1.5B
$D042 = 'PENDING'   # D-042 runtime is Ollama, llama.cpp removed
$D043 = 'PENDING'   # D-043 chat UI built before Step 7, ungrounded until the index exists
$D044 = 'PENDING'   # D-044 chat UI carries the page-level BM25 retrieval prototype
$D054 = 'PENDING'   # D-054 embedder: bge-small-en-v1.5 (rule 9: only you decide this)
$D039 = 'PENDING'   # D-039 three-model download: SUPERSEDE it with D-040, or APPROVE it

# Tag step-02-approved as well? Set to $false if step 02 is not finished to your eye.
$AcceptStep2 = $false

# ---------------------------------------------------------------------------
$Today = (Get-Date).ToString('yyyy-MM-dd')
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Decisions = [ordered]@{
    'D-038' = $D038; 'D-040' = $D040; 'D-042' = $D042; 'D-043' = $D043; 'D-044' = $D044
    'D-054' = $D054; 'D-039' = $D039
}

function Write-TextFile {
    param([string]$Path, [string[]]$Lines)
    # UTF-8 without BOM: PowerShell 5.1's -Encoding UTF8 writes a BOM, which would
    # show up as a stray character at the top of APPROVALS.md.
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, (($Lines -join "`n") + "`n"), $encoding)
}

function Invoke-Git {
    # Git writes benign notices to stderr ("LF will be replaced by CRLF"), and with
    # $ErrorActionPreference = 'Stop' PowerShell 5.1 turns a native command's stderr
    # into a terminating NativeCommandError. Read it as text and judge by exit code.
    param([string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = @(& git @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($code -ne 0) {
        throw ("git " + ($Arguments -join ' ') + " failed:`n" + ($output -join "`n"))
    }
    return $output
}

function Add-LogLine {
    # Newest first: insert the block directly under the log's Format line.
    param([string[]]$Lines, [string[]]$NewLines)
    # Plain prefix match on purpose: `-like` treats a backtick as its own escape
    # character, so the literal pattern 'Format: `YYYY-MM-DD*' never matched the
    # line it was written for.
    $marker = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -like 'Format:*') { $marker = $i; break }
    }
    if ($marker -lt 0) { throw 'APPROVALS.md: could not find the log Format line' }
    $insertAt = $marker + 2          # Format line, then the blank line under it
    $before = $Lines[0..($insertAt - 1)]
    $after = if ($insertAt -lt $Lines.Count) { $Lines[$insertAt..($Lines.Count - 1)] } else { @() }
    return @($before) + @($NewLines) + @($after)
}

function Test-LogLine {
    param([string[]]$Lines, [string]$Step, [string]$Action)
    $pattern = '\|\s+' + $Action + '\s+\|\s+' + [regex]::Escape($Step) + '\s+\| owner'
    foreach ($line in $Lines) { if ($line -match $pattern) { return $true } }
    return $false
}

# --- 1. gates ---------------------------------------------------------------
Push-Location $Root
try {
    $dirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0) { throw 'git status failed; is this a git repository?' }
    if ($dirty) {
        Write-Host 'REFUSING TO RUN: the working tree is not clean.' -ForegroundColor Red
        Write-Host 'Commit or revert these first - the script commits by name and will not touch them:' -ForegroundColor Red
        $dirty | ForEach-Object { Write-Host ('  ' + $_) }
        exit 1
    }

    $pending = @($Decisions.Keys | Where-Object { $Decisions[$_] -eq 'PENDING' })
    if ($pending.Count -gt 0) {
        if (-not $WhatIfPreference) {
            Write-Host 'REFUSING TO RUN: these decisions are still PENDING:' -ForegroundColor Red
            $pending | ForEach-Object { Write-Host ('  ' + $_) }
            Write-Host 'Open this file and set each one to APPROVE or REJECT. A decision approved by a script is not an approval.' -ForegroundColor Red
            exit 1
        }
        Write-Host ('WHAT IF: a real run would refuse, because these are still PENDING: ' + ($pending -join ', ')) -ForegroundColor Yellow
    }
    $unclear = @($Decisions.Keys | Where-Object { $Decisions[$_] -notin @('PENDING', 'APPROVE', 'REJECT') })
    if ($unclear.Count -gt 0) { throw ('unclear decision value for: ' + ($unclear -join ', ') + ' - use APPROVE or REJECT') }

    # --- 2. APPROVALS.md ----------------------------------------------------
    $approvals = Join-Path $Root 'APPROVALS.md'
    $lines = [System.IO.File]::ReadAllLines($approvals)
    # Steps 02 and 05 are worked on in the record without a start line: step 02 has a
    # completion but no start, and step 05's retrieval work (commit e873131) has neither.
    # Both are included so the log stops claiming those steps were never started. Any
    # line already present is skipped, so this list can stay complete as steps are added.
    $wanted = @(
        @{ Step = 'step 05'; Action = 'start' },
        @{ Step = 'step 04'; Action = 'start' },
        @{ Step = 'step 03'; Action = 'start' },
        @{ Step = 'step 02'; Action = 'start' },
        @{ Step = 'step 02'; Action = 'completion' },
        @{ Step = 'step 01'; Action = 'completion' }
    )
    $added = @()
    foreach ($entry in $wanted) {
        if (Test-LogLine -Lines $lines -Step $entry.Step -Action $entry.Action) {
            Write-Host ('skip    APPROVALS.md already has ' + $entry.Action + ' ' + $entry.Step)
        } else {
            $added += ('{0} | {1} | {2} | owner' -f $Today, $entry.Action, $entry.Step)
        }
    }
    if ($added.Count -gt 0 -and $PSCmdlet.ShouldProcess('APPROVALS.md', ('add ' + $added.Count + ' approval line(s): ' + ($added -join '; ')))) {
        Write-TextFile -Path $approvals -Lines (Add-LogLine -Lines $lines -NewLines $added)
        Invoke-Git @('add', '--', 'APPROVALS.md') | Out-Null
        Invoke-Git @('commit', '-m', 'OWNER: record step 01 and 02 completion and the start of steps 02, 03, 04 and 05') | Out-Null
        Write-Host ('added   ' + ($added -join ', ')) -ForegroundColor Green
        Write-Host 'committed APPROVALS.md'
    }

    # --- 3. tags ------------------------------------------------------------
    $tags = @('step-00-approved', 'step-01-approved')
    if ($AcceptStep2) { $tags += 'step-02-approved' }
    Write-Host ''
    Write-Host 'NOTE: these tags point at the current HEAD commit. There is no historical' -ForegroundColor Yellow
    Write-Host 'completion commit for step 00/01/02 to tag: those completions were only ever' -ForegroundColor Yellow
    Write-Host 'recorded in APPROVALS.md, and it was never committed. A tag here marks "approved' -ForegroundColor Yellow
    Write-Host 'as of this commit", not the original completion date.' -ForegroundColor Yellow
    $existingTags = @(& git tag -l)
    foreach ($tag in $tags) {
        if ($existingTags -contains $tag) {
            Write-Host ('skip    tag ' + $tag + ' already exists')
        } elseif ($PSCmdlet.ShouldProcess('git', ('create tag ' + $tag + ' at HEAD'))) {
            Invoke-Git @('tag', '-a', $tag, '-m', ('Step ' + $tag.Substring(5, 2) + ' completion approved by the owner')) | Out-Null
            Write-Host ('tagged  ' + $tag) -ForegroundColor Green
        }
    }

    # --- 4. DECISIONS.md ----------------------------------------------------
    $decisionsPath = Join-Path $Root 'DECISIONS.md'
    $decisionLines = [System.IO.File]::ReadAllLines($decisionsPath)
    $approved = @('D-038', 'D-040', 'D-042', 'D-043', 'D-044')
    $insertions = [ordered]@{}
    foreach ($id in $approved) {
        if ($Decisions[$id] -ne 'APPROVE') {
            Write-Host ('skip    ' + $id + ' is ' + $Decisions[$id] + ', no APPROVED line added')
            continue
        }
        $existing = @($decisionLines | Where-Object { $_ -like ('- **APPROVED ' + $id + ' by the owner*') })
        if ($existing.Count -gt 0) { Write-Host ('skip    ' + $id + ' already has an APPROVED line'); continue }
        $insertions[$id] = ('- **APPROVED {0} by the owner {1}.** The owner set the {0} variable in `artifacts/owner-kit/apply-owner-actions.ps1` to APPROVE; the entry above is unchanged.' -f $id, $Today)
    }
    if ($Decisions['D-039'] -eq 'PENDING') {
        Write-Host 'skip    D-039 is PENDING, no SUPERSEDED line added'
    } elseif (@($decisionLines | Where-Object { $_ -like '- **SUPERSEDED D-039*' }).Count -eq 0) {
        $insertions['D-039'] = ('- **SUPERSEDED D-039 by D-040 ({0}).** The owner declined the three-model download, and D-040 chose the model already on disk, so the candidates proposed here were never downloaded and no comparison was measured.' -f $Today)
    } else {
        Write-Host 'skip    D-039 already has a SUPERSEDED line'
    }

    if ($insertions.Count -gt 0) {
        $out = New-Object System.Collections.Generic.List[string]
        foreach ($line in $decisionLines) {
            $out.Add($line)
            foreach ($id in @($insertions.Keys)) {
                if ($line -like ('- **PROPOSED ' + $id + ' *') -or $line -like ('- **PROPOSED by agent, pending owner*' + $id + '*')) {
                    $out.Add($insertions[$id])
                }
            }
        }
        $missing = @($insertions.Keys | Where-Object { -not ($out -contains $insertions[$_]) })
        if ($missing.Count -gt 0) { throw ('could not find the entry line(s) for ' + ($missing -join ', ') + ' in DECISIONS.md') }
        if ($PSCmdlet.ShouldProcess('DECISIONS.md', ('add ' + $insertions.Count + ' approval line(s) for ' + ($insertions.Keys -join ', ')))) {
            Write-TextFile -Path $decisionsPath -Lines $out.ToArray()
            Invoke-Git @('add', '--', 'DECISIONS.md') | Out-Null
            Invoke-Git @('commit', '-m', 'OWNER: approve decisions D-038, D-040, D-042, D-043 and D-044 and supersede D-039') | Out-Null
            Write-Host ('added   ' + ($insertions.Keys -join ', ')) -ForegroundColor Green
            Write-Host 'committed DECISIONS.md'
        }
    }

    # --- 5. what to check next ---------------------------------------------
    Write-Host ''
    Write-Host 'Done. Verify with the two checks from APPROVALS.md (run them yourself):'
    # Check A and B both need a previous tag. Naming step-02-approved hard-coded made
    # those commands fail whenever $AcceptStep2 is false and the tag was not created.
    $prevTag = if ($tags -contains 'step-02-approved') { 'step-02-approved' } else { 'step-01-approved' }
    Write-Host ("  git log {0}..HEAD --invert-grep --grep=`"^OWNER:`" --name-only --format=`"%h %s`" -- AGENTS.md PLAN.md REQUIREMENTS.md APPROVALS.md" -f $prevTag)
    Write-Host ("  git diff -U0 {0}..HEAD -- EVAL.md DECISIONS.md steps eval/questions.jsonl | Select-String `"^-`" | Where-Object {{ $_ -notmatch `"^--- `" }}" -f $prevTag)
    Write-Host 'Check A must print nothing; every removed line in check B must be a ticked checkbox.'
    Write-Host ''
    Write-Host 'Left for you by hand (the script cannot do these): the 20-page and 20-table'
    Write-Host 'reviews in artifacts\step3\, then ticking the Step 3 boxes.'
} finally {
    Pop-Location
}
