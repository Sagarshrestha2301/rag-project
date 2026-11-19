# Add one PDF to the corpus and rebuild the page index, in one step.
#
# Usage:
#   .\scripts\add-document.ps1 -Path C:\inbox\2019_report.pdf
#   .\scripts\add-document.ps1 -Path data\raw\reports\2019_report.pdf      # keeps "reports\"
#   .\scripts\add-document.ps1 -Path C:\inbox\scan.pdf -Folder reports\2019
#
# What it does:
#   1. refuses anything that is not a PDF, and refuses a file name the corpus already
#      has (the loader identifies a document by name, so a duplicate is an error, not
#      a second copy);
#   2. puts the file at data\corpus\<folder>\<name>.pdf, hardlinked to the original when
#      both are on the same volume (D-030: no extra disk) and copied when they are not;
#   3. ingests it with python -m ingest.pipeline build, which parses ONLY new or changed
#      documents, then chunks and embeds them, and prints the document and page counts
#      before and after, with the measured time.
#
# The folder: a file under data\raw\ keeps its folder relative to data\raw; anything
# else goes to the corpus root unless -Folder names a folder. data\raw is owner-only and
# is never modified here.
#
# The 97-document / 851-page corpus took 1414 s for a first full ingest (OCR about 4 s per
# scanned page); adding one more document re-parses just that document. A file whose bytes
# or pages repeat one already indexed is flagged as a duplicate and skipped, not silently
# indexed twice - `python -m ingest.pipeline status` lists it.
#
# Usage note for tests: -Python exists so the script can be pointed at a different
# interpreter, the same way scripts\open-chat.ps1 does.

param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$Folder = "",
    [string]$Python = ".venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

# --- offline mode (D-026): nothing here downloads anything, and the build must not try
$env:HF_HUB_OFFLINE       = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_DATASETS_OFFLINE  = "1"

$root   = Split-Path -Parent $PSScriptRoot
$corpus = Join-Path $root "data\corpus"
$raw    = Join-Path $root "data\raw"
$index  = Join-Path $root "index\pages.json"
Set-Location $root

function Stop-With([string]$Message) {
    Write-Host "refused: $Message" -ForegroundColor Red
    exit 1
}

# --- the source file -------------------------------------------------------------
if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    Stop-With "no such file: $Path"
}
$source = (Resolve-Path -LiteralPath $Path).Path
if ([IO.Path]::GetExtension($source) -ne ".pdf") {
    Stop-With "'$source' is not a .pdf. Convert Word files with the pinned LibreOffice to <name>.docx.pdf first."
}
if (-not (Test-Path -LiteralPath $corpus)) {
    Stop-With "the corpus folder is missing: $corpus"
}
$corpusFull = (Resolve-Path -LiteralPath $corpus).Path
if ($source.StartsWith($corpusFull + [IO.Path]::DirectorySeparatorChar)) {
    Stop-With "'$source' is already inside data\corpus."
}

$name = [IO.Path]::GetFileName($source)

# --- the folder it keeps ---------------------------------------------------------
$rawFull = $null
if (Test-Path -LiteralPath $raw) { $rawFull = (Resolve-Path -LiteralPath $raw).Path }
$relative = ""
if ($rawFull -and $source.StartsWith($rawFull + [IO.Path]::DirectorySeparatorChar)) {
    $relative = Split-Path -Parent $source.Substring($rawFull.Length + 1)
}
elseif ($Folder -ne "") {
    if ([IO.Path]::IsPathRooted($Folder) -or $Folder -match "(^|[\\/])\.\.([\\/]|$)") {
        Stop-With "-Folder must be a relative folder inside data\corpus, not '$Folder'."
    }
    $relative = $Folder.TrimStart("\", "/")
}

$targetDir = if ($relative -eq "") { $corpusFull } else { Join-Path $corpusFull $relative }
$target    = Join-Path $targetDir $name

# --- duplicate file name, refused the way corpus.files() refuses it --------------
$duplicates = @(Get-ChildItem -LiteralPath $corpusFull -Recurse -File -Filter "*.pdf" |
                Where-Object { $_.Name -eq $name })
if ($duplicates.Count -gt 0) {
    $where = ($duplicates | ForEach-Object { $_.FullName }) -join " and "
    Stop-With "duplicate corpus file name '$name': $where. Documents are identified by name, so rename one of them."
}

# --- counts before ---------------------------------------------------------------
$beforeText = "no index yet"
if (Test-Path -LiteralPath $index) {
    try {
        $before = Get-Content -LiteralPath $index -Raw -Encoding UTF8 | ConvertFrom-Json
        $beforeText = "$($before.docs.Count) documents / $($before.pages.Count) pages"
    }
    catch {
        $beforeText = "index unreadable, will be rebuilt"
    }
}

# --- put it in place: hardlink when the volume allows, copy otherwise ------------
if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}
$mode = "hardlink"
try {
    New-Item -ItemType HardLink -Path $target -Value $source -ErrorAction Stop | Out-Null
}
catch {
    Copy-Item -LiteralPath $source -Destination $target -Force
    $mode = "copy (hardlink failed: $($_.Exception.Message))"
}
$bytes = (Get-Item -LiteralPath $target).Length

# --- ingest it -------------------------------------------------------------------
Write-Host "added  : $target  ($mode, $([math]::Round($bytes / 1MB, 2)) MB)"
Write-Host "index  : ingesting from $beforeText - only new or changed documents are parsed"
$started = Get-Date
$json = & $Python -m ingest.pipeline build
if ($LASTEXITCODE -ne 0) {
    Stop-With "the ingestion failed (exit $LASTEXITCODE). The file is in place; fix the error and run: .venv\Scripts\python.exe -m ingest.pipeline build"
}
$after = (($json -join "`n") | ConvertFrom-Json)
$elapsed = [int]((Get-Date) - $started).TotalSeconds

Write-Host "before : $beforeText"
Write-Host "after  : $($after.stages.assemble.documents) documents / $($after.stages.assemble.pages) pages  ($($after.stages.parse.parsed) parsed, $($after.stages.embed.chunks) chunks embedded in $elapsed s)"
if ($after.stages.parse.failed -gt 0 -or $after.counts.duplicate -gt 0) {
    Write-Host "check  : $($after.stages.parse.failed) failed document(s) and $($after.counts.duplicate) duplicate(s) - .venv\Scripts\python.exe -m ingest.pipeline status"
}
Write-Host ""
Write-Host "search it: .venv\Scripts\python.exe -m generation.answer `"<a question about $name>`""
exit 0
