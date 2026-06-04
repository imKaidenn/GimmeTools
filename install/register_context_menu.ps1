<#
.SYNOPSIS
    Register MediaTools context menu entries in Windows Explorer.

.DESCRIPTION
    Adds right-click options for image and video files:
      - "Remove Background" (images)
      - "Upscale Image (4x)" (images)
      - "Process Video" (videos)

    Uses HKCU (current user, no admin required) by default.
    Use -AllUsers for HKLM (requires admin).

.EXAMPLE
    .\install\register_context_menu.ps1
    .\install\register_context_menu.ps1 -AllUsers
#>

param(
    [switch]$AllUsers   # Register for all users (requires admin)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ToolkitRoot = Split-Path -Parent $ScriptDir
$VenvPython  = Join-Path $ToolkitRoot "tools\venv\Scripts\python.exe"

# Verify venv exists
if (-not (Test-Path $VenvPython)) {
    Write-Host "Error: venv not found. Run install\setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Decide registry hive
if ($AllUsers) {
    $Hive = "HKLM:"
    # Check admin
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")
    if (-not $isAdmin) {
        Write-Host "Error: -AllUsers requires running as Administrator." -ForegroundColor Red
        exit 1
    }
} else {
    $Hive = "HKCU:"
}

$ImageExts = @(".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp")
$VideoExts = @(".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v")

function Register-Entry {
    param(
        [string]$Extension,
        [string]$MenuName,
        [string]$Script,
        [string]$Icon
    )

    $command = "`"$VenvPython`" `"$Script`" `"%1`""

    # SystemFileAssociations path works for all files of that extension
    $keyPath = "$Hive\Software\Classes\SystemFileAssociations\$Extension\shell\MediaTools.$($MenuName -replace ' ','')"
    $cmdPath = "$keyPath\command"

    if (-not (Test-Path $keyPath)) {
        New-Item -Path $keyPath -Force | Out-Null
    }
    Set-ItemProperty -Path $keyPath -Name "(Default)" -Value "MediaTools: $MenuName"

    if ($Icon) {
        Set-ItemProperty -Path $keyPath -Name "Icon" -Value $Icon
    }

    if (-not (Test-Path $cmdPath)) {
        New-Item -Path $cmdPath -Force | Out-Null
    }
    Set-ItemProperty -Path $cmdPath -Name "(Default)" -Value $command
}

Write-Host ""
Write-Host "Registering context menu entries..." -ForegroundColor Cyan

$removeBgScript  = Join-Path $ToolkitRoot "scripts\remove_bg.py"
$upscaleScript   = Join-Path $ToolkitRoot "scripts\upscale_image.py"
$videoScript     = Join-Path $ToolkitRoot "scripts\process_video.py"

$count = 0

# Image entries
foreach ($ext in $ImageExts) {
    Register-Entry -Extension $ext -MenuName "Remove Background" -Script $removeBgScript -Icon ""
    Register-Entry -Extension $ext -MenuName "Upscale Image (4x)" -Script $upscaleScript -Icon ""
    $count += 2
}

# Video entries
foreach ($ext in $VideoExts) {
    Register-Entry -Extension $ext -MenuName "Process Video" -Script $videoScript -Icon ""
    $count++
}

Write-Host ""
Write-Host "Done: $count context menu entries registered." -ForegroundColor Green
Write-Host "Right-click any image or video file in Explorer to see the new options." -ForegroundColor White
Write-Host ""
Write-Host "To unregister: .\install\unregister_context_menu.ps1" -ForegroundColor Gray
Write-Host ""
