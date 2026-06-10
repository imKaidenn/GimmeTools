<#
.SYNOPSIS
    Remove all GimmeTools context menu entries from Windows Explorer.

.EXAMPLE
    .\install\unregister_context_menu.ps1
    .\install\unregister_context_menu.ps1 -AllUsers
#>

param(
    [switch]$AllUsers
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($AllUsers) {
    $Hive = "HKLM:"
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")
    if (-not $isAdmin) {
        Write-Host "Error: -AllUsers requires running as Administrator." -ForegroundColor Red
        exit 1
    }
} else {
    $Hive = "HKCU:"
}

$AllExts = @(".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp",
             ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v")

$MenuNames = @("RemoveBackground", "UpscaleImage(4x)", "ProcessVideo")

$removed = 0

# "MediaTools." entries were written by v1.0 — clean those up too.
foreach ($ext in $AllExts) {
    foreach ($name in $MenuNames) {
        foreach ($prefix in @("GimmeTools", "MediaTools")) {
            $keyPath = "$Hive\Software\Classes\SystemFileAssociations\$ext\shell\$prefix.$name"
            if (Test-Path $keyPath) {
                Remove-Item -Path $keyPath -Recurse -Force
                $removed++
            }
        }
    }
}

if ($removed -gt 0) {
    Write-Host "Removed $removed context menu entries." -ForegroundColor Green
} else {
    Write-Host "No GimmeTools context menu entries found." -ForegroundColor Yellow
}
