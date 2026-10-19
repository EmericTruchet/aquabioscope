# Construit le paquet Microsoft Store (MSIX) d'AquaBioScope a partir de la
# compilation PyInstaller en mode dossier (dist\AquaBioScope, voir
# AquaBioScope-installer.spec).
#
# Le paquet n'a pas besoin d'etre signe pour etre soumis au Store : c'est
# Microsoft qui le signe apres certification (d'ou l'absence d'alerte
# SmartScreen pour les utilisateurs qui installent depuis le Store).
#
# Usage (valeurs a recopier depuis l'espace partenaires, Produit >
# Gestion des produits > Identite du produit) :
#   .\store\build_msix.ps1 -IdentityName "12345EmericTruchet.AquaBioScope" `
#       -Publisher "CN=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX" -PublisherDisplayName "Emeric Truchet"
# Resultat : dist\AquaBioScope.msix (a televerser dans la soumission Store).
param(
    [Parameter(Mandatory = $true)][string]$IdentityName,
    [Parameter(Mandatory = $true)][string]$Publisher,
    [Parameter(Mandatory = $true)][string]$PublisherDisplayName,
    [string]$Version = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $root "dist\AquaBioScope"
if (-not (Test-Path (Join-Path $appDir "AquaBioScope.exe"))) {
    throw "Compilation introuvable : lancer d'abord pyinstaller AquaBioScope-installer.spec"
}

if (-not $Version) {
    $Version = (Select-String -Path (Join-Path $root "src\aquabioscope\__init__.py") -Pattern '"([0-9.]+)"').Matches[0].Groups[1].Value
}
# Le Store impose 4 nombres, le dernier a 0.
$parts = @($Version.Split(".") | ForEach-Object { [int]$_ })
while ($parts.Count -lt 3) { $parts += 0 }
$msixVersion = "{0}.{1}.{2}.0" -f $parts[0], $parts[1], $parts[2]

$staging = Join-Path $root "build\msix"
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
New-Item -ItemType Directory -Force $staging | Out-Null
Copy-Item -Recurse -Path (Join-Path $appDir "*") -Destination $staging
Copy-Item -Recurse -Path (Join-Path $PSScriptRoot "Assets") -Destination $staging

$manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot "AppxManifest.xml")
$manifest = $manifest.Replace("{IDENTITY_NAME}", $IdentityName).Replace("{PUBLISHER}", $Publisher)
$manifest = $manifest.Replace("{PUBLISHER_DISPLAY_NAME}", $PublisherDisplayName).Replace("{VERSION}", $msixVersion)
[System.IO.File]::WriteAllText((Join-Path $staging "AppxManifest.xml"), $manifest, (New-Object System.Text.UTF8Encoding $false))

$makeappx = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\makeappx.exe" |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeappx) { throw "makeappx.exe introuvable (installer le SDK Windows 10/11)" }

$output = Join-Path $root "dist\AquaBioScope.msix"
& $makeappx.FullName pack /d $staging /p $output /o
if ($LASTEXITCODE -ne 0) { throw "makeappx a echoue ($LASTEXITCODE)" }
Write-Host "Paquet Store cree : $output (version $msixVersion)"
