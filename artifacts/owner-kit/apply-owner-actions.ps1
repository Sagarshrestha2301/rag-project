<#
    apply-owner-actions.ps1  -  OWNER ONLY. An agent must never run or edit this file.

    Purpose: bring APPROVALS.md, the git tags and DECISIONS.md up to date in one
    reviewable run, instead of leaving the record behind what actually happened.

    What it does, in order:
      1. refuses to run if the working tree is not clean, or if any decision below
         still says 'PENDING';
      2. adds the missing approval lines to APPROVALS.md and commits them: completion
         for steps 01, 02, 04 and 05, start for steps 02, 03, 04, 05 and 06;
      3. creates step-00-approved, step-01-approved, step-02-approved, step-04-approved
         and step-05-approved (each gated by a switch below);
      4. writes one verdict line for every decision in the table below - 19 rows as
         shipped, 18 APPROVED and one SUPERSEDED - and commits them;
      5. prints the two verification commands from APPROVALS.md.

    Each decision has exactly one line in the table, so the record cannot end up with
    a decision that was read but never answered. Change 'PENDING' to 'APPROVE',
    'REJECT' or 'SUPERSEDE' after reading that decision in DECISIONS.md. PENDING means
    "I have not decided yet", and the script will not act on a decision you have not
    made.

    Dry run (changes nothing, prints what it would do):
        powershell -NoProfile -ExecutionPolicy Bypass -File artifacts\owner-kit\apply-owner-actions.ps1 -WhatIf

    Real run:
        powershell -NoProfile -ExecutionPolicy Bypass -File artifacts\owner-kit\apply-owner-actions.ps1
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Your decisions. Each entry is one decision: Id, Verdict, Why.
# Verdict is 'PENDING', 'APPROVE', 'REJECT', or 'SUPERSEDE' (then By = the id that
# replaces it). 'Why' is the sentence that will appear in DECISIONS.md, so it has to
# be true of the entry above it. Evidence for each one is in OWNER-CHECKLIST.md.
# ---------------------------------------------------------------------------
$Decisions = @(
    # --- Step 2: which model answers, and what was measured ---------------------
    @{ Id = 'D-039'; Verdict = 'APPROVE';   Why = 'Two of the three candidates were downloaded and measured after all: qwen3.5 4b (3.3 GB) and phi4-mini (2.5 GB), both in D-047. Gemma 4 E2B was not downloaded, and the earlier note claiming none of them were is corrected by this line.' }
    @{ Id = 'D-040'; Verdict = 'APPROVE';   Why = 'Recorded as the choice made on 2026-11-13: 496.8 tok/s prompt, 8.6 tok/s generation, 3,505 MiB of 4,096 MiB peak. D-048 later moves the generator to the 4B on measured evidence and keeps this model as the fallback, so this entry stands as history rather than as the current setting.' }
    @{ Id = 'D-046'; Verdict = 'SUPERSEDE'; By = 'D-047'; Why = 'Its title says two candidates will never be measured, and that stopped being true on 2026-11-14 when the owner asked for the comparison and D-047 filled both blank rows. Approving both entries would record two contradictory statements; D-047 is the table that stands.' }
    @{ Id = 'D-047'; Verdict = 'APPROVE';   Why = 'The comparison exists and was measured on this machine, temperature 0, num_ctx 4096: qwen3.5 4B 23/30, qwen2.5 7B 18/30, phi4-mini 16/30, with citations 20/30, 15/30 and 14/30.' }
    @{ Id = 'D-048'; Verdict = 'APPROVE';   Why = 'Justified by D-047 (23/30 against 18/30, citations 20/30 against 15/30) and already how the system runs: qwen3.5:4b with thinking off, the 7B kept as the fallback.' }

    # --- Step 3: how pages are read --------------------------------------------
    @{ Id = 'D-045'; Verdict = 'APPROVE';   Why = 'OCR runs at index build for pages with no text layer: 86 of 851 pages, 16-23 s for 4 pages, and pages that stay unreadable are reported (20 of 851) rather than silently dropped.' }
    @{ Id = 'D-049'; Verdict = 'APPROVE';   Why = 'Parser per page type, measured on this corpus: PyMuPDF grid filled from the page own words gives 393/393 numeric tokens on table pages and 5,511/5,520 across the corpus, and OCR for the 4 NARAYAN pages.' }

    # --- Step 4: chunks, metadata and the embedder -----------------------------
    @{ Id = 'D-038'; Verdict = 'APPROVE';   Why = 'Already how the corpus grew: Stage A (one document), then Stage B (97 documents, 851 pages), with the eval re-baselined at each growth.' }
    @{ Id = 'D-050'; Verdict = 'APPROVE';   Why = 'How the chunker works, as built: section-bounded text chunks and one table per chunk, 3,226 chunks from 95 documents.' }
    @{ Id = 'D-051'; Verdict = 'APPROVE';   Why = 'Heading detection reads two shapes and rejects four trap families; 0 chunks cross a heading across the 16 structure cases, and the guard test can fail.' }
    @{ Id = 'D-052'; Verdict = 'APPROVE';   Why = 'Text chunks are paragraph-atomic with the cap stronger than the overlap, so no chunk ends mid-sentence and no record carries a bad page range.' }
    @{ Id = 'D-053'; Verdict = 'APPROVE';   Why = 'One table is one chunk, and table text is kept out of prose chunks by geometry plus content, so the same numbers cannot be retrieved twice.' }
    @{ Id = 'D-054'; Verdict = 'APPROVE';   Why = 'bge-small-en-v1.5: ties multilingual-e5-small on recall@5 (23/26 each), differs by 0.021 MRR (0.702 against 0.723), and is 134 MB against 493 MB.' }
    @{ Id = 'D-055'; Verdict = 'APPROVE';   Why = 'Captions 32 to 37 and units 37 to 52 of 268 table chunks, with the measured ceiling kept in view: 210 detected tables have no printed caption within 160 points.' }

    # --- Step 5: retrieval -----------------------------------------------------
    @{ Id = 'D-056'; Verdict = 'APPROVE';   Why = 'Measured over 79 saved weight configurations (eval/runs/2026-11-16-sweep/): page BM25 alone keeps 25/26 at MRR 0.885, the best fusion reaches 23/26 at 0.432, and no fusion beats the baseline - the four that reach 25/26 are exactly the ones with chunk and dense at zero. The hybrid stays in the repository as evidence, and the UI keeps the simpler retriever.' }
    @{ Id = 'D-057'; Verdict = 'APPROVE';   Why = 'Withdraws two figures D-056 quoted (24/26 at 0.832 and 24/26 at 0.486) that no artifact supports and that do not reproduce; the saved sweep replaces them and the decision to keep page BM25 stands, now on stronger evidence.' }

    # --- Runtime and UI --------------------------------------------------------
    @{ Id = 'D-042'; Verdict = 'APPROVE';   Why = 'Same weights, same 3,394-token prompt: Ollama 499.1 tok/s prompt and 9.43 tok/s generation against llama-server 293.1 and 7.46, and the llama.cpp build is already removed.' }
    @{ Id = 'D-043'; Verdict = 'APPROVE';   Why = 'The UI exists in ui/, answers and streams, and says on screen when an answer is ungrounded instead of pretending to cite.' }
    @{ Id = 'D-044'; Verdict = 'APPROVE';   Why = 'Page-level BM25 in the UI scores 25/26 at MRR 0.885, better than every dense embedding measured so far (best 23/26 at 0.723); it is a prototype, not Step 5.' }
)

# Tag step-02-approved as well? Set to $false if step 02 is not finished to your eye.
$AcceptStep2 = $true

# Step 4's 10-chunk inspection was approved in chat on 2026-11-16, so its completion
# line and tag belong in the same run. Set to $false to leave Step 4 open.
$AcceptStep4 = $true

# Step 5 finished on 2026-11-16 as well: all seven DoD boxes are ticked, the baseline
# is re-based on the 45-question dev set, and the offline proof passed. Set to $false to
# leave Step 5 open (for example while you write the last five dev questions).
$AcceptStep5 = $true

# Opening Step 6 is a start, not a completion: no tag is created for it, because a step
# is tagged only when its definition of done is finished. Set to $false to keep Step 6
# closed (for example while you decide the not-found gate and the generator).
$StartStep6 = $true

# ---------------------------------------------------------------------------
$Today = (Get-Date).ToString('yyyy-MM-dd')
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

$Verdicts = @('PENDING', 'APPROVE', 'REJECT', 'SUPERSEDE')

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

function Get-VerdictLine {
    # One line per decision, in the style D-041 already uses. It goes *above* the
    # PROPOSED bullet: inserting it below the header would split the entry from the
    # indented body that belongs to it.
    param([hashtable]$Decision, [string]$Date)
    switch ($Decision.Verdict) {
        'APPROVE'   { return ('- **APPROVED {0} by the owner {1}.** {2}' -f $Decision.Id, $Date, $Decision.Why) }
        'REJECT'    { return ('- **REJECTED {0} by the owner {1}.** {2}' -f $Decision.Id, $Date, $Decision.Why) }
        'SUPERSEDE' { return ('- **SUPERSEDED {0} by {1} ({2}).** {3}' -f $Decision.Id, $Decision.By, $Date, $Decision.Why) }
        default     { throw ('Get-VerdictLine called with verdict ' + $Decision.Verdict) }
    }
}

# --- 0. validate the table before touching anything -------------------------
$ids = @($Decisions | ForEach-Object { $_.Id })
$dupes = @($ids | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name })
if ($dupes.Count -gt 0) { throw ('a decision appears twice in $Decisions: ' + ($dupes -join ', ')) }
foreach ($d in $Decisions) {
    if (-not $d.Id) { throw 'a decision entry has no Id' }
    if ($d.Verdict -notin $Verdicts) { throw ('unclear verdict for ' + $d.Id + ': ' + $d.Verdict + ' - use PENDING, APPROVE, REJECT or SUPERSEDE') }
    if (-not $d.Why) { throw ('no Why for ' + $d.Id + ' - every verdict needs the sentence that justifies it') }
    if ($d.Verdict -eq 'SUPERSEDE' -and -not $d.By) { throw ('SUPERSEDE for ' + $d.Id + ' needs By = the id that replaces it') }
    if ($d.By -and ($ids -notcontains $d.By)) { throw ($d.Id + ' is superseded by ' + $d.By + ', which is not a decision in this table') }
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

    $pending = @($Decisions | Where-Object { $_.Verdict -eq 'PENDING' } | ForEach-Object { $_.Id })
    if ($pending.Count -gt 0) {
        if (-not $WhatIfPreference) {
            Write-Host 'REFUSING TO RUN: these decisions are still PENDING:' -ForegroundColor Red
            $pending | ForEach-Object { Write-Host ('  ' + $_) }
            Write-Host 'Open this file and set each one to APPROVE, REJECT or SUPERSEDE. A decision approved by a script is not an approval.' -ForegroundColor Red
            exit 1
        }
        Write-Host ('WHAT IF: a real run would refuse, because these are still PENDING: ' + ($pending -join ', ')) -ForegroundColor Yellow
    }

    # --- 2. APPROVALS.md ----------------------------------------------------
    $approvals = Join-Path $Root 'APPROVALS.md'
    $lines = [System.IO.File]::ReadAllLines($approvals)
    # Steps 02 and 05 were worked on with no start line in the record: step 02 has a
    # completion but no start, and step 05's retrieval work (commit e873131) has neither.
    # Any line already present is skipped, so this list can stay complete as steps are added.
    $wanted = @(
        @{ Step = 'step 05'; Action = 'start' },
        @{ Step = 'step 04'; Action = 'start' },
        @{ Step = 'step 03'; Action = 'start' },
        @{ Step = 'step 02'; Action = 'start' },
        @{ Step = 'step 06'; Action = 'start' },
        @{ Step = 'step 05'; Action = 'completion' },
        @{ Step = 'step 04'; Action = 'completion' },
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
        Invoke-Git @('commit', '-m', 'OWNER: record the start of steps 02-06 and the completion of steps 01, 02, 04 and 05') | Out-Null
        Write-Host ('added   ' + ($added -join ', ')) -ForegroundColor Green
        Write-Host 'committed APPROVALS.md'
    }

    # --- 3. tags ------------------------------------------------------------
    $tags = @('step-00-approved', 'step-01-approved')
    if ($AcceptStep2) { $tags += 'step-02-approved' }
    if ($AcceptStep4) { $tags += 'step-04-approved' }
    if ($AcceptStep5) { $tags += 'step-05-approved' }
    Write-Host ''
    Write-Host 'NOTE: these tags point at the current HEAD commit. There is no historical' -ForegroundColor Yellow
    Write-Host 'completion commit for step 00/01/02 to tag: those completions were only ever' -ForegroundColor Yellow
    Write-Host 'recorded in APPROVALS.md. A tag here marks "approved as of this commit", not' -ForegroundColor Yellow
    Write-Host 'the original completion date.' -ForegroundColor Yellow
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
    $insertions = [ordered]@{}
    foreach ($d in $Decisions) {
        if ($d.Verdict -eq 'PENDING') { Write-Host ('skip    ' + $d.Id + ' is PENDING, no verdict line added'); continue }
        # Any verdict already recorded for this id counts, whatever it says, so a
        # second run cannot append a contradicting line.
        $pattern = '^\- \*\*(APPROVED|REJECTED|SUPERSEDED) ' + [regex]::Escape($d.Id) + '(\s|$|\()'
        $existing = @($decisionLines | Where-Object { $_ -match $pattern })
        if ($existing.Count -gt 0) { Write-Host ('skip    ' + $d.Id + ' already has a verdict line'); continue }
        $insertions[$d.Id] = (Get-VerdictLine -Decision $d -Date $Today)
    }

    if ($insertions.Count -gt 0) {
        $out = New-Object System.Collections.Generic.List[string]
        $placed = @{}
        foreach ($line in $decisionLines) {
            foreach ($id in @($insertions.Keys)) {
                # Above the PROPOSED bullet, so the entry keeps its indented body.
                if ($line -like ('- **PROPOSED ' + $id + ' *')) {
                    $out.Add($insertions[$id])
                    $placed[$id] = $true
                }
            }
            $out.Add($line)
        }
        $missing = @($insertions.Keys | Where-Object { -not $placed.ContainsKey($_) })
        if ($missing.Count -gt 0) { throw ('could not find the PROPOSED entry line(s) for ' + ($missing -join ', ') + ' in DECISIONS.md') }

        $approvedCount = @($Decisions | Where-Object { $_.Verdict -eq 'APPROVE' }).Count
        $rejectedCount = @($Decisions | Where-Object { $_.Verdict -eq 'REJECT' }).Count
        $supersededIds = @($Decisions | Where-Object { $_.Verdict -eq 'SUPERSEDE' } | ForEach-Object { $_.Id })
        $message = 'OWNER: record {0} decisions ({1} approved, {2} rejected, {3} superseded: {4})' -f `
            $insertions.Count, $approvedCount, $rejectedCount, $supersededIds.Count, ($supersededIds -join ', ')

        if ($PSCmdlet.ShouldProcess('DECISIONS.md', ('add ' + $insertions.Count + ' verdict line(s) for ' + ($insertions.Keys -join ', ')))) {
            Write-TextFile -Path $decisionsPath -Lines $out.ToArray()
            Invoke-Git @('add', '--', 'DECISIONS.md') | Out-Null
            Invoke-Git @('commit', '-m', $message) | Out-Null
            Write-Host ('added   ' + ($insertions.Keys -join ', ')) -ForegroundColor Green
            Write-Host ('committed DECISIONS.md: ' + $message)
        }
    }

    # --- 5. what to check next ---------------------------------------------
    Write-Host ''
    Write-Host 'Done. Verify with the two checks from APPROVALS.md (run them yourself):'
    # Check A and B both need a previous tag. Naming step-02-approved hard-coded made
    # those commands fail whenever $AcceptStep2 is false and the tag was not created.
    $prevTag = if ($tags -contains 'step-05-approved') { 'step-05-approved' }
               elseif ($tags -contains 'step-04-approved') { 'step-04-approved' }
               elseif ($tags -contains 'step-02-approved') { 'step-02-approved' }
               else { 'step-01-approved' }
    Write-Host ("  git log {0}..HEAD --invert-grep --grep=`"^OWNER:`" --name-only --format=`"%h %s`" -- AGENTS.md PLAN.md REQUIREMENTS.md APPROVALS.md" -f $prevTag)
    Write-Host ("  git diff -U0 {0}..HEAD -- EVAL.md DECISIONS.md steps eval/questions.jsonl | Select-String `"^-`" | Where-Object {{ $_ -notmatch `"^--- `" }}" -f $prevTag)
    Write-Host 'Check A must print nothing; every removed line in check B must be a ticked checkbox.'
    Write-Host ''
    Write-Host 'Left for you by hand (the script cannot do these): the 20-page and 20-table'
    Write-Host 'reviews in artifacts\step3\, then ticking the Step 3 boxes.'
} finally {
    Pop-Location
}
