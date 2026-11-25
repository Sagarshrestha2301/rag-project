# One-line health check: model server, chat UI, corpus index.
#
# Usage:
#   .\scripts\health.ps1
#   .\scripts\health.ps1 -UiPort 8001 -Model qwen3.5:4b
#
# Prints a status line and exits 0 only when all three parts are ready:
#
#   READY  model=qwen3.5:4b loaded  ui=127.0.0.1:8000 ok  index=97 docs/851 pages  (34 ms)
#
# When something is not ready it also prints one machine-readable reasons line,
# so a wrapper script can log why instead of only seeing exit code 1:
#
#   NOT READY  model=qwen3.5:4b loaded  ui=down  index=unverified  (2187 ms)
#   REASONS  ui=unreachable(127.0.0.1:8099)  index=unverified(ui down)
#
# Every run also appends one line to logs\health.log, ready or not, with a local
# timestamp. Failures alone would show a drop but never its recovery, so both are
# written and a gap in time is visible as a gap in timestamps. -NoLog skips the
# file; -LogPath writes somewhere else. The file rotates to health.log.1 at 1 MB,
# so an all-day polling loop cannot grow without bound.
#
#  2026-11-15T10:52:31+05:45  READY      model=qwen3.5:4b loaded  ui=127.0.0.1:8000 ok  index=97 docs/851 pages
#  2026-11-15T10:57:04+05:45  NOT READY  model=qwen3.5:4b loaded  ui=down  index=unverified  REASONS ui=unreachable(127.0.0.1:8000)
#
# Reasons are space-separated `part=reason(detail)` tokens on a single line, so
# `... | Select-String '^REASONS'` captures the whole list.
#
# Checks, in order, and what each proves:
#   model : GET /api/ps on the Ollama port, and the model must be resident. Ollama
#           answering is not enough - a model that is installed but not loaded
#           makes the first question wait for a cold start.
#   ui    : GET /api/health on the chat server. A port that accepts a connection
#           but returns nothing usable still counts as down.
#   index : index/ui-pages.json on disk, plus the page and document counts the UI
#           reports, so a UI running against an empty index cannot look healthy.
#
# Exit code 0 = ready, 1 = at least one part is not ready. Nothing here starts
# anything: it only reads.

param(
    [int]    $UiPort = 8000,
    [int]    $OllamaPort = 11434,
    [string] $Model = "qwen3.5:4b",
    [switch] $NoLog,
    [string] $LogPath = "logs\health.log",
    [int]    $MaxLogBytes = 1MB
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Follow a port pinned with $env:UI_PORT unless -UiPort was given explicitly.
if (-not $PSBoundParameters.ContainsKey('UiPort') -and $env:UI_PORT) {
    $UiPort = [int]$env:UI_PORT
}

$watch = [System.Diagnostics.Stopwatch]::StartNew()
$problems = 0
$reasons = [System.Collections.Generic.List[string]]::new()

# --- model ---
$modelText = "$Model not-loaded"
try {
    $ps = Invoke-RestMethod -Uri "http://127.0.0.1:$OllamaPort/api/ps" -TimeoutSec 3
    $names = @($ps.models | ForEach-Object { $_.name })
    $match = $names | Where-Object { $_ -eq $Model -or $_ -eq "$Model`:latest" } | Select-Object -First 1
    if ($match) {
        $modelText = "$match loaded"
    } else {
        $problems++
        $reasons.Add("model=not-loaded($Model)")
    }
} catch {
    $modelText = "server-down"
    $problems++
    $reasons.Add("model=unreachable(127.0.0.1:$OllamaPort)")
}

# --- ui ---
$uiText = "down"
$ui = $null
try {
    $ui = Invoke-RestMethod -Uri "http://127.0.0.1:$UiPort/api/health" -TimeoutSec 5
    if ($ui.ok) {
        $uiText = "127.0.0.1:$UiPort ok"
    } else {
        $problems++
        $reasons.Add("ui=not-ok(127.0.0.1:$UiPort)")
    }
} catch {
    $problems++
    $reasons.Add("ui=unreachable(127.0.0.1:$UiPort)")
}

# --- index ---
# A file on disk is not a working index, but a missing file is worse than an
# unchecked one, so the two cases say different things: with the UI down the
# counts cannot be read, and calling that "missing" would be a lie.
$indexFile = Join-Path $root "index\ui-pages.json"
if (-not (Test-Path $indexFile)) {
    $indexText = "missing"
    $problems++
    $reasons.Add("index=missing(index\ui-pages.json)")
} elseif ($ui -and $ui.pages -gt 0 -and $ui.documents -gt 0) {
    $indexText = "$($ui.documents) docs/$($ui.pages) pages"
} else {
    $indexText = "unverified"
    $problems++
    $reasons.Add("index=unverified(ui down)")
}

$watch.Stop()
$verdict = if ($problems -eq 0) { "READY" } else { "NOT READY" }
$summary = "model={0}  ui={1}  index={2}" -f $modelText, $uiText, $indexText
Write-Host ("{0}  {1}  ({2} ms)" -f $verdict, $summary, $watch.ElapsedMilliseconds)
if ($problems -gt 0) {
    Write-Host ("REASONS  {0}" -f ($reasons -join "  "))
}

# --- log line ---
if (-not $NoLog) {
    try {
        $logFile = if ([System.IO.Path]::IsPathRooted($LogPath)) { $LogPath } else { Join-Path $root $LogPath }
        $logDir = Split-Path -Parent $logFile
        if ($logDir) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
        if ((Test-Path $logFile) -and (Get-Item $logFile).Length -ge $MaxLogBytes) {
            Move-Item -Path $logFile -Destination "$logFile.1" -Force
        }
        $stamp = (Get-Date).ToString("yyyy-MM-dd'T'HH:mm:sszzz")
        $line = "{0}  {1}  {2}" -f $stamp, $verdict.PadRight(9), $summary
        if ($problems -gt 0) { $line += "  REASONS " + ($reasons -join "  ") }
        # .NET append with an explicit BOM-less UTF-8 encoding: PowerShell 5.1's
        # Add-Content -Encoding UTF8 writes a BOM, which then sits in front of the
        # first timestamp and breaks grep/awk on the first line of the file.
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::AppendAllText($logFile, $line + "`r`n", $utf8)
    } catch {
        # A health check must still report on stdout if the log cannot be written.
        Write-Host "WARN  health log not written: $($_.Exception.Message)"
    }
}

exit $(if ($problems -eq 0) { 0 } else { 1 })
