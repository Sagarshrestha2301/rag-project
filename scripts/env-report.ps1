# Step 0 environment record.
# Re-run with:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\env-report.ps1
# Read-only: prints facts, changes nothing.

$ErrorActionPreference = "Stop"

$os      = Get-CimInstance Win32_OperatingSystem
$computer = Get-CimInstance Win32_ComputerSystem
$cpu     = Get-CimInstance Win32_Processor
$drives  = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"

"Reported at : {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")
"OS          : {0} (build {1})" -f $os.Caption, $os.BuildNumber
"CPU         : {0} ({1} cores / {2} threads)" -f $cpu.Name.Trim(), $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors
"RAM         : {0} GB" -f [math]::Round($computer.TotalPhysicalMemory / 1GB, 1)
""
"Disk (fixed drives):"
foreach ($d in $drives) {
    "  {0} free {1} GB of {2} GB" -f $d.DeviceID, [math]::Round($d.FreeSpace / 1GB, 1), [math]::Round($d.Size / 1GB, 1)
}
""
"GPU (nvidia-smi):"
& nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,compute_cap --format=csv,noheader
"CUDA (driver-reported):"
(& nvidia-smi | Select-String -Pattern "CUDA Version").ToString().Trim()
""
"python      : {0}" -f (& python --version 2>&1)
"pip         : {0}" -f ((& python -m pip --version 2>&1) -split " ")[1]
"git         : {0}" -f (& git --version)
"LibreOffice : {0}" -f (Get-Item "C:\Program Files\LibreOffice\program\soffice.exe").VersionInfo.ProductVersion
