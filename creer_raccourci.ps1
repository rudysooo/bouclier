param([string]$Target, [string]$ScriptPath, [string]$WorkDir, [string]$Icon = '')
$ErrorActionPreference = 'Stop'
$WorkDir = $WorkDir.TrimEnd('\').Trim('"')
$ScriptPath = $ScriptPath.Trim('"')
$Target = $Target.Trim('"')
if (-not (Test-Path -LiteralPath $Target)) { throw "Interpreteur Python introuvable : $Target" }
if (-not (Test-Path -LiteralPath $ScriptPath)) { throw "Script introuvable : $ScriptPath" }

$shell = New-Object -ComObject WScript.Shell
$folders = @()
$folders += [Environment]::GetFolderPath('Desktop')               # Bureau (gere OneDrive / redirections)
$folders += [Environment]::GetFolderPath('Programs')              # Menu Demarrer
$created = $false
foreach ($folder in ($folders | Where-Object { $_ } | Select-Object -Unique)) {
    try {
        if (-not (Test-Path -LiteralPath $folder)) { New-Item -ItemType Directory -Path $folder -Force | Out-Null }
        $path = Join-Path $folder 'Bouclier v3.0.lnk'
        $link = $shell.CreateShortcut($path)
        $link.TargetPath = $Target
        $link.Arguments = '"' + $ScriptPath + '"'
        $link.WorkingDirectory = $WorkDir
        $link.Description = 'Bouclier v3.0 - Anonymisation OCR de documents et images'
        if ($Icon -and (Test-Path -LiteralPath $Icon)) { $link.IconLocation = $Icon }
        $link.Save()
        if (Test-Path -LiteralPath $path) { Write-Output "LNK:$path"; $created = $true }
        else { Write-Output "Raccourci non retrouve apres creation : $path" }
    } catch {
        Write-Output "Echec dans '$folder' : $($_.Exception.Message)"
    }
}
if (-not $created) { exit 1 }
