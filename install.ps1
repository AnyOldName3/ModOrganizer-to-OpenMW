[CmdletBinding()]
param (
    [Parameter(Mandatory=$true)]
    [string]
    $InstallPath
)

python -m PyQt5.pylupdate_main OpenMWExport.py -ts OpenMWExport_en.ts

if (!$?) {
    Write-Error "pylupdate failed." -ErrorAction Stop
}

Copy-Item OpenMWExport.py,openmw.ico $InstallPath -ErrorAction Stop

Write-Output "Done."