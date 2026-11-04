# Windows-Installer bauen (CI und Test-VM). Erwartet das fertige PyInstaller-Programm in dist\SH-Tunebridge.
#   pwsh scripts/build-windows-setup.ps1 -Version 0.7.1 -OutDir out
# Lädt Inno Setup (feste Version + Prüfsumme) und den WebView2-Bootstrapper von Microsoft (Signatur wird geprüft).
param(
  [Parameter(Mandatory = $true)][string]$Version,
  [string]$SrcDir = "dist\SH-Tunebridge",
  [string]$OutDir = "out"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Work = Join-Path $Root "build\windows-setup"
New-Item -ItemType Directory -Force $Work, (Join-Path $Root $OutDir) | Out-Null
$ProgressPreference = "SilentlyContinue"

# Inno Setup 6.7.3 (Prüfsumme = von GitHub veröffentlichter Digest)
$IsUrl = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
$IsSha = "9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732"
$IsDir = Join-Path $Work "inno"
$Iscc = Join-Path $IsDir "ISCC.exe"
if (-not (Test-Path $Iscc)) {
  $IsExe = Join-Path $Work "innosetup.exe"
  Invoke-WebRequest $IsUrl -OutFile $IsExe
  if ((Get-FileHash $IsExe -Algorithm SHA256).Hash -ne $IsSha) { throw "Inno Setup: Prüfsumme falsch" }
  $p = Start-Process $IsExe -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/PORTABLE=1", "/DIR=`"$IsDir`"" -Wait -PassThru
  if ($p.ExitCode -ne 0 -or -not (Test-Path $Iscc)) { throw "Inno Setup ließ sich nicht entpacken (Code $($p.ExitCode))" }
}

# WebView2-Bootstrapper von Microsoft – nur mit gültiger Microsoft-Signatur
$Wv2 = Join-Path $Work "MicrosoftEdgeWebview2Setup.exe"
Invoke-WebRequest "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $Wv2
$sig = Get-AuthenticodeSignature -LiteralPath $Wv2
if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "O=Microsoft Corporation") {
  throw "WebView2-Bootstrapper: Signatur ungültig ($($sig.Status))"
}

$Src = (Resolve-Path (Join-Path $Root $SrcDir)).Path
$Out = (Resolve-Path (Join-Path $Root $OutDir)).Path
& $Iscc "/Q" "/DMyVersion=$Version" "/DSrcDir=$Src" "/DWebView2=$Wv2" "/DOutDir=$Out" (Join-Path $Root "packaging\windows\sh-tunebridge.iss")
if ($LASTEXITCODE) { throw "ISCC fehlgeschlagen ($LASTEXITCODE)" }
Get-Item (Join-Path $Out "SH-Tunebridge-$Version-windows-setup.exe") | Select-Object Name, Length
