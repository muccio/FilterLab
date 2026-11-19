<#
.SYNOPSIS
    FilterLab Windows Standalone Executable & Installer Build Script
#>

[CmdletBinding()]
param (
    [switch]$SkipInstaller = $false
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$Version = "1.0.0"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " FilterLab Windows Standalone Packaging Pipeline" -ForegroundColor Cyan
Write-Host " Project Root: $ProjectRoot" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$VenvCandidates = @(
    (Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"),
    (Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\Activate.ps1")
)
foreach ($VenvPath in $VenvCandidates) {
    if (Test-Path $VenvPath) {
        Write-Host "Activating virtual environment at $VenvPath..." -ForegroundColor Yellow
        & $VenvPath
        break
    }
}

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Error "PyInstaller is not found in PATH or the active Python virtual environment."
    exit 1
}

$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }

$IconPath = Join-Path $ProjectRoot "packaging\assets\icon.ico"
if (-not (Test-Path $IconPath)) {
    python (Join-Path $ProjectRoot "packaging\generate_assets.py")
}

$SpecFile = Join-Path $ProjectRoot "packaging\filterlab.spec"
Write-Host "Executing PyInstaller with spec: $SpecFile..." -ForegroundColor Green
Set-Location $ProjectRoot
pyinstaller --noconfirm --clean $SpecFile

$ExeOutput = Join-Path $DistDir "FilterLab\FilterLab.exe"
if (-not (Test-Path $ExeOutput)) {
    Write-Error "Build failed: $ExeOutput was not generated."
    exit 1
}

Write-Host "Testing compiled executable (--check-build)..." -ForegroundColor Green
& $ExeOutput --check-build
if ($LASTEXITCODE -ne 0) {
    Write-Error "--check-build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

$PortableZip = Join-Path $DistDir "FilterLab-$Version-windows-x64-portable.zip"
Compress-Archive -Path (Join-Path $DistDir "FilterLab") -DestinationPath $PortableZip -Force
Write-Host "Portable ZIP created at: $PortableZip" -ForegroundColor Green

if (-not $SkipInstaller) {
    $IssPath = Join-Path $ProjectRoot "packaging\installer.iss"
    $IsccCandidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
    )
    $IsccExe = $IsccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

    if ($IsccExe) {
        Write-Host "Compiling Windows Installer using Inno Setup ($IsccExe)..." -ForegroundColor Cyan
        & $IsccExe $IssPath
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Inno Setup failed with exit code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "Installer compiled successfully in $DistDir!" -ForegroundColor Green
    } else {
        Write-Warning "Inno Setup (ISCC.exe) not found. Skipping installer generation."
    }
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " FilterLab Windows Build Pipeline Finished." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
