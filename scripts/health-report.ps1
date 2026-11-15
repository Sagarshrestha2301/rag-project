# Summarise logs\health.log into uptime windows: when each part was down, for how long.
#
# Usage:
#   .\scripts\health-report.ps1
#   .\scripts\health-report.ps1 -LogPath logs\health.log -GapSeconds 120
#
# Reads the rotated file (`health.log.1`) first when it exists, so a window that
# spans a rotation is still reported. Output is one block per part:
#
#   health log : logs\health.log (+ health.log.1)
#   checks     : 7 from 2026-11-15T10:30:00+05:45 to 2026-11-15T11:00:00+05:45 (30 min)
#
#   part    windows
#   model   1 window, 3 min 12 s total
#           10:41:03 -> 10:44:15   3 min 12 s
#   ui      none
#   index   none
#   NOW     READY
#
# Two honest limits, printed with the report:
#   - a window can only be measured between two checks, so a real outage may start
#     later and end earlier than the report says;
#   - if the gap between checks is longer than -GapSeconds (default 300), the
#     window is marked `(gap)` because the outage is only known to lie inside it.
#
# Exit code 0 always: this reports, it does not judge. Nothing here changes a file.

param(
    [string] $LogPath = "logs\health.log",
    [int]    $GapSeconds = 300
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$current = if ([System.IO.Path]::IsPathRooted($LogPath)) { $LogPath } else { Join-Path $root $LogPath }
$files = @()
foreach ($candidate in @("$current.1", $current)) {
    if (Test-Path $candidate) { $files += $candidate }
}
if ($files.Count -eq 0) {
    Write-Host "no log at $current - run .\scripts\health.ps1 at least once"
    exit 0
}

$rows = @()
foreach ($file in $files) {
    foreach ($line in Get-Content -Path $file -Encoding UTF8) {
        if ($line -notmatch '^(?<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})\s+(?<verdict>READY|NOT READY)\s+(?<rest>.*)$') {
            continue
        }
        $rows += [pscustomobject]@{
            When    = [datetimeoffset]::Parse($Matches.ts)
            Verdict = $Matches.verdict.Trim()
            Rest    = $Matches.rest
        }
    }
}
$rows = $rows | Sort-Object When
if ($rows.Count -eq 0) {
    Write-Host "no parseable lines in $current"
    exit 0
}

function Get-State($row, [string]$part) {
    $rest = $row.Rest
    switch ($part) {
        "model" {
            if ($rest -match 'model=server-down' -or $rest -match 'model=\S+ not-loaded') { return $false }
            return $true
        }
        "ui" {
            if ($rest -match 'ui=down' -or $rest -match 'ui=not-ok') { return $false }
            return $true
        }
        "index" {
            if ($rest -match 'index=missing' -or $rest -match 'index=unverified') { return $false }
            return $true
        }
    }
    return $true
}

function Format-Duration([timespan]$span) {
    if ($span.TotalSeconds -lt 60) { return "{0:N0} s" -f $span.TotalSeconds }
    if ($span.TotalMinutes -lt 60) { return "{0:N0} min {1:N0} s" -f [math]::Floor($span.TotalMinutes), $span.Seconds }
    return "{0:N0} h {1:N0} min" -f [math]::Floor($span.TotalHours), $span.Minutes
}

$first = $rows[0].When
$last = $rows[-1].When
$span = ($last - $first)
Write-Host "health log : $($files -join ' + ')"
Write-Host ("checks     : {0} from {1:yyyy-MM-ddTHH:mm:sszzz} to {2:yyyy-MM-ddTHH:mm:sszzz} ({3})" -f `
    $rows.Count, $first, $last, (Format-Duration $span))
Write-Host ""

foreach ($part in @("model", "ui", "index")) {
    $windows = @()
    $downAt = $null
    $prev = $null
    foreach ($row in $rows) {
        $up = Get-State $row $part
        $gap = if ($prev) { ($row.When - $prev).TotalSeconds -gt $GapSeconds } else { $false }
        if (-not $up -and $null -eq $downAt) { $downAt = $row.When }
        if ($up -and $null -ne $downAt) {
            $windows += [pscustomobject]@{ Start = $downAt; End = $row.When; Gap = $gap }
            $downAt = $null
        }
        if (-not $up) { $lastDownGap = $gap }
        $prev = $row.When
    }
    if (-not (Get-Variable -Name lastDownGap -ValueOnly -ErrorAction SilentlyContinue)) { $lastDownGap = $false }
    if ($null -ne $downAt) {
        $windows += [pscustomobject]@{ Start = $downAt; End = $null; Gap = $lastDownGap }
    }

    if ($windows.Count -eq 0) {
        Write-Host ("{0,-7} none" -f $part)
        continue
    }

    $closed = @($windows | Where-Object { $_.End })
    $total = [timespan]::Zero
    foreach ($w in $closed) { $total += ($w.End - $w.Start) }
    # @() around the filter: a single matching object has no .Count in PS 5.1, and
    # the count silently disappeared from the header because of it.
    $open = @($windows | Where-Object { -not $_.End })
    $label = "{0} window{1}" -f $windows.Count, $(if ($windows.Count -eq 1) { "" } else { "s" })
    if ($closed.Count -gt 0) { $label += ", " + (Format-Duration $total) + " total" }
    if ($open.Count -gt 0) { $label += ", " + $open.Count + " still down at last check" }
    Write-Host ("{0,-7} {1}" -f $part, $label)

    foreach ($w in $windows) {
        if ($w.End) {
            $dur = Format-Duration ($w.End - $w.Start)
            $mark = if ($w.Gap) { "  (gap: may be shorter)" } else { "" }
            Write-Host ("        {0:HH:mm:ss} -> {1:HH:mm:ss}   {2}{3}" -f $w.Start, $w.End, $dur, $mark)
        } else {
            Write-Host ("        {0:HH:mm:ss} -> still down at last check (length unknown)" -f $w.Start)
        }
    }
}

$gaps = 0
for ($i = 1; $i -lt $rows.Count; $i++) {
    if (($rows[$i].When - $rows[$i - 1].When).TotalSeconds -gt $GapSeconds) { $gaps++ }
}
Write-Host ""
Write-Host ("NOW     {0}" -f $rows[-1].Verdict)
Write-Host ("limits  windows are measured between checks; {0} gap(s) over {1} s, marked (gap)" -f $gaps, $GapSeconds)
Write-Host "        index is only verifiable through the UI, so its windows mirror ui when the UI is down"
