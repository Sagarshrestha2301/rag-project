# Summarise logs\health.log into per-part uptime: when each part was down, for how
# long, and what share of the observed window it was up.
#
# Usage:
#   .\scripts\health-report.ps1
#   .\scripts\health-report.ps1 -LogPath logs\health.log -GapSeconds 120
#
# Reads the rotated file (`health.log.1`) first when it exists, so a window that
# spans a rotation is still reported. Example output:
#
#   health log : logs\health.log + logs\health.log.1
#   checks     : 7 from 2026-11-15T10:30:00+05:45 to 2026-11-15T11:00:00+05:45 (30 min 0 s)
#
#   part    windows                                              uptime
#   model   none                                                 100.0%
#   ui      2 windows, 1 min 30 s total                          95.0%
#           10:41:03 -> 10:42:03   1 min 0 s
#           10:58:30 -> 10:59:00   30 s  (gap: may be shorter)
#   index   2 windows, 1 min 30 s total                          95.0%
#           ...
#
#   NOW     READY
#   limits  windows are measured between checks; 0 gap(s) over 300 s, marked (gap)
#           index is only verifiable through the UI, so its windows mirror ui when the UI is down
#
# Adding a part is one entry in `$Parts` below: id, the regex that marks it down,
# and an optional note printed under the limits. State encoded in the log line is
# the only input, so the report and `scripts/health.ps1` stay independent.
#
# Limits, printed with the report:
#   - a window can only be measured between two checks, so a real outage may start
#     later and end earlier than the report says;
#   - if the gap between checks is longer than -GapSeconds (default 300), the
#     window is marked `(gap)` because the outage is only known to lie inside it;
#   - uptime is optimistic for the same reason: unchecked time counts as up.
#
# Exit code 0 always: this reports, it does not judge. Nothing here changes a file.

param(
    [string] $LogPath = "logs\health.log",
    [int]    $GapSeconds = 300
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# --- registry: the single place a part is described -------------------------
$Parts = @(
    @{ Id = "model"; DownPattern = 'model=server-down|model=\S+ not-loaded'
       Note = $null }
    @{ Id = "ui";    DownPattern = 'ui=down|ui=not-ok'
       Note = $null }
    @{ Id = "index"; DownPattern = 'index=missing|index=unverified'
       Note = "index is only verifiable through the UI, so its windows mirror ui when the UI is down" }
)

# TODO(step-07): when a fourth part is added, move the down-pattern vocabulary into
# a file both scripts dot-source, so a new reason token is written once instead of
# in scripts\health.ps1 (producer) and here (consumer).
# TODO(step-07): read health.log.2+ if retention ever keeps more than one rotation;
# a window that starts before the oldest file is currently dropped, not reported.

function Read-HealthRows {
    param([string[]]$Files)
    $parsed = @()
    foreach ($file in $Files) {
        foreach ($line in Get-Content -Path $file -Encoding UTF8) {
            if ($line -notmatch '^(?<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})\s+(?<verdict>READY|NOT READY)\s+(?<rest>.*)$') {
                continue
            }
            $parsed += [pscustomobject]@{
                When    = [datetimeoffset]::Parse($Matches.ts)
                Verdict = $Matches.verdict.Trim()
                Rest    = $Matches.rest
            }
        }
    }
    return @($parsed | Sort-Object When)
}

function Test-PartUp {
    param($Row, [string]$DownPattern)
    return -not ($Row.Rest -match $DownPattern)
}

function Get-PartWindows {
    param($Rows, [string]$DownPattern)
    $windows = @()
    $downAt = $null
    $lastDownGap = $false
    $prev = $null
    foreach ($row in $Rows) {
        $gap = if ($prev) { ($row.When - $prev).TotalSeconds -gt $GapSeconds } else { $false }
        $up = Test-PartUp -Row $row -DownPattern $DownPattern
        if (-not $up -and $null -eq $downAt) { $downAt = $row.When }
        if ($up -and $null -ne $downAt) {
            $windows += [pscustomobject]@{ Start = $downAt; End = $row.When; Gap = $gap }
            $downAt = $null
        }
        if (-not $up) { $lastDownGap = $gap }
        $prev = $row.When
    }
    if ($null -ne $downAt) {
        $windows += [pscustomobject]@{ Start = $downAt; End = $null; Gap = $lastDownGap }
    }
    return @($windows)
}

# Named $SpanStart/$SpanEnd rather than $First/$Last: `$Last` collided with the
# caller's scope and the subtraction failed with "no overload for op_Subtraction",
# which is the kind of error a shadowed automatic name produces.
function Measure-Windows {
    param($Windows, [datetimeoffset]$SpanStart, [datetimeoffset]$SpanEnd)
    # An empty window list arrives as $null, and `$null | Where-Object { ... }`
    # yields ONE null element (measured: count 1, element null), so filtering a
    # null list used to hand a null window to `$SpanEnd - $w.Start` and throw
    # "no overload for op_Subtraction". Drop nulls before any property access.
    $items = @($Windows | Where-Object { $null -ne $_ })
    $down = [timespan]::Zero
    foreach ($w in @($items | Where-Object { $_.End })) { $down += ($w.End - $w.Start) }
    # A window still open at the last check counts up to that check and no further.
    foreach ($w in @($items | Where-Object { -not $_.End })) { $down += ($SpanEnd - $w.Start) }

    $span = $SpanEnd - $SpanStart
    # One check, or several at the same instant, cannot define an uptime: dividing
    # by a zero span would either throw or print a fake 100%.
    $uptime = if ($span.TotalSeconds -le 0) { "n/a" } else {
        # 0.0/100.0, not 0/100: PowerShell binds [math]::Min to the int overload,
        # which rounded 16.6667 to 17 before the string was formatted (measured:
        # Min(100, 16.6667) returns 17). Doubles keep the fraction.
        $pct = [math]::Max(0.0, [math]::Min(100.0, (1.0 - ($down.TotalSeconds / $span.TotalSeconds)) * 100.0))
        "{0:N1}%" -f $pct
    }
    return [pscustomobject]@{ Down = $down; Uptime = $uptime }
}

function Format-Duration {
    param([timespan]$Span)
    if ($Span.TotalSeconds -lt 60) { return "{0:N0} s" -f $Span.TotalSeconds }
    if ($Span.TotalMinutes -lt 60) { return "{0:N0} min {1:N0} s" -f [math]::Floor($Span.TotalMinutes), $Span.Seconds }
    return "{0:N0} h {1:N0} min" -f [math]::Floor($Span.TotalHours), $Span.Minutes
}

# --- read ------------------------------------------------------------------
$current = if ([System.IO.Path]::IsPathRooted($LogPath)) { $LogPath } else { Join-Path $root $LogPath }
$files = @(@("$current.1", $current) | Where-Object { Test-Path $_ })
if ($files.Count -eq 0) {
    Write-Host "no log at $current - run .\scripts\health.ps1 at least once"
    exit 0
}

$rows = @(Read-HealthRows -Files $files)   # @(): one row would otherwise lose .Count
if ($rows.Count -eq 0) {
    Write-Host "no parseable lines in $current"
    exit 0
}

$first = $rows[0].When
$last = $rows[-1].When
Write-Host "health log : $($files -join ' + ')"
Write-Host ("checks     : {0} from {1:yyyy-MM-ddTHH:mm:sszzz} to {2:yyyy-MM-ddTHH:mm:sszzz} ({3})" -f `
    $rows.Count, $first, $last, (Format-Duration ($last - $first)))
Write-Host ""
Write-Host ("{0,-7} {1,-50} {2}" -f "part", "windows", "uptime")

# --- render: one loop over the registry, no per-part special cases ----------
$notes = @()
foreach ($part in $Parts) {
    # @() at the call site: a function returning an empty array produces $null.
    $windows = @(Get-PartWindows -Rows $rows -DownPattern $part.DownPattern)
    $measured = Measure-Windows -Windows $windows -SpanStart $first -SpanEnd $last

    if ($windows.Count -eq 0) {
        Write-Host ("{0,-7} {1,-50} {2}" -f $part.Id, "none", $measured.Uptime)
        if ($part.Note) { $notes += $part.Note }
        continue
    }

    # @() around each filter: a single matching object has no .Count in PS 5.1.
    $open = @($windows | Where-Object { -not $_.End })
    $summary = "{0} window{1}" -f $windows.Count, $(if ($windows.Count -eq 1) { "" } else { "s" })
    if ($measured.Down.TotalSeconds -gt 0) { $summary += ", " + (Format-Duration $measured.Down) + " down" }
    if ($open.Count -gt 0) { $summary += ", " + $open.Count + " still down" }
    Write-Host ("{0,-7} {1,-50} {2}" -f $part.Id, $summary, $measured.Uptime)

    foreach ($w in $windows) {
        if ($w.End) {
            $mark = if ($w.Gap) { "  (gap: may be shorter)" } else { "" }
            Write-Host ("        {0:HH:mm:ss} -> {1:HH:mm:ss}   {2}{3}" -f $w.Start, $w.End, (Format-Duration ($w.End - $w.Start)), $mark)
        } else {
            Write-Host ("        {0:HH:mm:ss} -> still down at last check (length unknown)" -f $w.Start)
        }
    }
    if ($part.Note) { $notes += $part.Note }
}

$gaps = 0
for ($i = 1; $i -lt $rows.Count; $i++) {
    if (($rows[$i].When - $rows[$i - 1].When).TotalSeconds -gt $GapSeconds) { $gaps++ }
}
Write-Host ""
Write-Host ("NOW     {0}" -f $rows[-1].Verdict)
Write-Host ("limits  windows are measured between checks; {0} gap(s) over {1} s, marked (gap)" -f $gaps, $GapSeconds)
Write-Host "        unchecked time counts as up, so uptime is the optimistic reading"
foreach ($note in $notes) { Write-Host "        $note" }
