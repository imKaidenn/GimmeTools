<#
.SYNOPSIS
    MediaTools setup (PowerShell wrapper).

.DESCRIPTION
    The real setup logic lives in install\setup.py (pure Python, no PowerShell
    dependency). This wrapper just finds a Python interpreter and runs it, so
    people who reach for setup.ps1 out of habit still work.

    You can also run setup directly without PowerShell:
        py install\setup.py
.EXAMPLE
    .\install\setup.ps1
#>

$ErrorActionPreference = "Stop"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ToolkitRoot = Split-Path -Parent $ScriptDir
$SetupPy     = Join-Path $ScriptDir "setup.py"

# Find a Python interpreter
$PythonCmd = $null
foreach ($candidate in @("py", "python", "python3")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            if ([int]$Matches[1] -ge 3 -and [int]$Matches[2] -ge 10) {
                $PythonCmd = $candidate
                break
            }
        }
    } catch { }
}

if (-not $PythonCmd) {
    Write-Host "Python 3.10+ not found." -ForegroundColor Red
    Write-Host "Install from https://www.python.org/downloads/ (tick 'Add to PATH')." -ForegroundColor Yellow
    exit 1
}

& $PythonCmd $SetupPy
exit $LASTEXITCODE
