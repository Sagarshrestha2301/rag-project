<#
    manual-to-pdf.ps1  -  turn docs/manual.html into docs/manual.pdf.

    Uses the Chromium already on this machine (Edge, else Chrome) in headless mode, so
    nothing is installed and no network call is made. The page's @media print block
    does the layout work: light palette, no navigation, tables unpinned from their
    scroll width, and rows/stages kept whole across page breaks.

    Build the HTML first, then print it:
        .venv\Scripts\python.exe reports\build_manual.py
        powershell -NoProfile -ExecutionPolicy Bypass -File scripts\manual-to-pdf.ps1

    Why the browser: LibreOffice is pinned here but renders this CSS poorly, and a PDF
    library is not installed. Chromium is already a dependency of the machine, not of
    the project.
#>

[CmdletBinding()]
param(
    [string]$Html = 'docs\manual.html',
    [string]$Out = 'docs\manual.pdf'
)

$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$HtmlPath = if ([System.IO.Path]::IsPathRooted($Html)) { $Html } else { Join-Path $Root $Html }
$OutPath = if ([System.IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path $Root $Out }

if (-not (Test-Path -LiteralPath $HtmlPath)) {
    throw ("no HTML at " + $HtmlPath + " - run: .venv\Scripts\python.exe reports\build_manual.py")
}

$candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe')
)
$browser = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $browser) { throw 'found neither Edge nor Chrome; install one or print the page by hand (Ctrl+P)' }

# A throwaway profile: headless Chromium refuses to share a profile that is in use,
# and this keeps the owner's real browsing profile untouched.
$profile = Join-Path $env:TEMP ('manual-pdf-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $profile -Force | Out-Null

# file:/// URI with forward slashes; Chromium wants an absolute path in the flag.
$uri = 'file:///' + ($HtmlPath -replace '\\', '/')
$outForward = $OutPath -replace '\\', '/'

Write-Host ('printing ' + $HtmlPath)
Write-Host ('  with   ' + (Split-Path -Leaf $browser) + ' (headless)')
Write-Host ('  to     ' + $OutPath)

try {
    $arguments = @(
        '--headless=new',
        '--disable-gpu',
        '--no-first-run',
        '--no-default-browser-check',
        '--no-pdf-header-footer',
        '--run-all-compositor-stages-before-draw',
        '--virtual-time-budget=8000',
        ('--user-data-dir=' + $profile),
        ('--print-to-pdf=' + $outForward),
        $uri
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        # Chromium writes progress and warnings to stderr even on success, so the exit
        # code and the file on disk are what decide, not the text.
        $output = @(& $browser @arguments 2>&1 | ForEach-Object { $_.ToString() })
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
} finally {
    Remove-Item -LiteralPath $profile -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $OutPath)) {
    throw ("the browser exited " + $code + " and wrote no PDF:`n" + ($output -join "`n"))
}

$bytes = [System.IO.File]::ReadAllBytes($OutPath)
if ($bytes.Length -lt 5 -or [System.Text.Encoding]::ASCII.GetString($bytes, 0, 5) -ne '%PDF-') {
    throw ('the file written is not a PDF: ' + $OutPath)
}

Write-Host ('wrote  ' + $OutPath + '  (' + [math]::Round($bytes.Length / 1KB, 1) + ' KB)')
