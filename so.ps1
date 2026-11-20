<#
  so.ps1 - run the SO-101 toolkit from PowerShell.

      .\so doctor          .\so record          .\so train          .\so rollout

  Activates the `lerobot` conda environment if it is not active yet, then runs
  `python -m sokit <your arguments>`.  `.\so --help` lists every command.
#>
$ErrorActionPreference = 'Stop'

if ($env:CONDA_DEFAULT_ENV -ne 'lerobot') {
    $hook = $null
    foreach ($base in @("$env:USERPROFILE\miniforge3", "$env:LOCALAPPDATA\miniforge3", "$env:USERPROFILE\miniconda3", "C:\ProgramData\miniforge3")) {
        $candidate = Join-Path $base 'shell\condabin\conda-hook.ps1'
        if (Test-Path $candidate) { $hook = $candidate; break }
    }
    if (-not $hook) {
        Write-Host "Cannot find Miniforge. Install it, or activate the 'lerobot' environment yourself and run: python -m sokit $args" -ForegroundColor Red
        exit 1
    }
    & $hook
    conda activate lerobot
    if ($env:CONDA_DEFAULT_ENV -ne 'lerobot') {
        Write-Host "The conda environment 'lerobot' does not exist. See README.md > Setup." -ForegroundColor Red
        exit 1
    }
}

$env:PYTHONUTF8 = '1'
# lerobot logs to stderr; never let PowerShell treat that as a terminating error.
$ErrorActionPreference = 'Continue'
$code = 1
Push-Location $PSScriptRoot
try {
    python -m sokit @args
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $code
