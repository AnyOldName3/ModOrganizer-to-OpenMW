[CmdletBinding()]
param (
    [Parameter(Mandatory=$true)]
    [string]
    $InstallPath,
    [switch] $Release
)

python -m PyQt5.pylupdate_main OpenMWExport.py -ts OpenMWExport_en.ts

if (!$?) {
    Write-Error "pylupdate failed." -ErrorAction Stop
}

if ( -Not (Test-Path -PathType Container $InstallPath)) {
    New-Item -ItemType Directory $InstallPath -ErrorAction Stop
}

Copy-Item OpenMWExport.py,openmw.ico $InstallPath -ErrorAction Stop

if ($Release) {
    Copy-Item LICENSE,README.md $InstallPath -ErrorAction Stop
}

Write-Output "Done."