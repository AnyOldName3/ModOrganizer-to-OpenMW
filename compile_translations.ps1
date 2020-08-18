$CurrentBranch = git branch --show-current

$TranslationBranches = git branch -r | Select-String "origin/translations"

if ( -Not (Get-Command lrelease 2>$null)) {
	Write-Error "lrelease unavialable, make sure it's in `$env:Path." -ErrorAction Stop
}

ForEach ($branch In $TranslationBranches) {
	git checkout ($branch.ToString().Trim())
	Push-Location translations
	Get-ChildItem *.ts | ForEach-Object { lrelease $_ }
	Pop-Location
}

git checkout $CurrentBranch