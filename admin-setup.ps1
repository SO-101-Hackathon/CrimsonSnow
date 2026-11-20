<#
.SYNOPSIS
  One-time, admin-only preparation of this Windows laptop for LeRobot / SO-101.

.DESCRIPTION
  Everything here needs elevation, so it lives in one script = one UAC prompt.
  Safe to re-run: each step checks whether it is already done.

  Always:
    Developer Mode  -> lets normal processes create symlinks. lerobot-train writes
                       `checkpoints/last` as a symlink and crashes without it
                       (OSError: [WinError 1314]). Takes effect immediately, no reboot.

  Only with -WithWSL (the hackathon guide's alternative Windows path; NOT needed for the
  native flow this repo uses, and USB cameras do not work inside WSL anyway):
    usbipd-win      -> shares USB devices (the arms) with WSL
    WSL 2 + Ubuntu  -> Linux environment; may ask for a reboot

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\admin-setup.ps1            (Developer Mode only)
  powershell -ExecutionPolicy Bypass -File .\admin-setup.ps1 -WithWSL

  Type it in any terminal opened in this folder (hackathon-shell.cmd works).
  "Right-click > Run with PowerShell" does NOT work while Windows has its default script
  policy: the window closes at once and nothing is changed.
#>
param(
    [switch]$WithWSL,
    [switch]$NoPause,
    [string]$Distro = 'Ubuntu-24.04',
    [string]$LogPath = "$PSScriptRoot\outputs\admin-setup.log"
)

$ErrorActionPreference = 'Continue'

function Test-Admin {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host 'Requesting administrator rights (accept the Windows prompt)...'
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-Distro', $Distro, '-LogPath', "`"$LogPath`"")
    if ($WithWSL) { $argList += '-WithWSL' }
    if ($NoPause) { $argList += '-NoPause' }
    try {
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $argList -Verb RunAs -Wait -PassThru
        Write-Host "Elevated run finished with exit code $($p.ExitCode). Log: $LogPath"
        exit $p.ExitCode
    } catch {
        Write-Host "Elevation was declined or failed: $($_.Exception.Message)"
        if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
        exit 1223
    }
}

New-Item -ItemType Directory -Force (Split-Path $LogPath) | Out-Null
$script:failed = 0
function Log($msg) {
    $line = "[{0:HH:mm:ss}] {1}" -f (Get-Date), $msg
    Write-Host $line
    Add-Content -Path $LogPath -Value $line -Encoding utf8
}

Log "=== admin-setup started on $env:COMPUTERNAME as $env:USERNAME ==="

# --- Developer Mode (unprivileged symlinks) ------------------------------------
try {
    $key = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock'
    if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
    $cur = (Get-ItemProperty -Path $key -ErrorAction SilentlyContinue).AllowDevelopmentWithoutDevLicense
    if ($cur -eq 1) {
        Log 'Developer Mode: already enabled'
    } else {
        Set-ItemProperty -Path $key -Name 'AllowDevelopmentWithoutDevLicense' -Value 1 -Type DWord
        Log 'Developer Mode: ENABLED (symlinks now work without elevation)'
    }
} catch {
    $script:failed++
    Log "Developer Mode: FAILED - $($_.Exception.Message)"
}

if ($WithWSL) {
    # --- usbipd-win ------------------------------------------------------------
    try {
        if (Test-Path "$env:ProgramFiles\usbipd-win\usbipd.exe") {
            Log 'usbipd-win: already installed'
        } else {
            Log 'usbipd-win: installing via winget...'
            winget install --exact --id dorssel.usbipd-win --silent --accept-package-agreements --accept-source-agreements --disable-interactivity | Out-Null
            if (Test-Path "$env:ProgramFiles\usbipd-win\usbipd.exe") {
                Log 'usbipd-win: installed'
            } else {
                $script:failed++
                Log "usbipd-win: winget exit code $LASTEXITCODE and usbipd.exe not found"
            }
        }
    } catch {
        $script:failed++
        Log "usbipd-win: FAILED - $($_.Exception.Message)"
    }

    # --- WSL 2 + Ubuntu ----------------------------------------------------------
    try {
        $env:WSL_UTF8 = '1'
        wsl.exe --status *> $null
        if ($LASTEXITCODE -ne 0) {
            Log 'WSL: installing the platform (wsl --install --no-distribution)...'
            wsl.exe --install --no-distribution | ForEach-Object { if ($_) { Log "  wsl: $_" } }
            Log "WSL: platform install exit code $LASTEXITCODE"
        } else {
            Log 'WSL: platform already installed'
        }
        wsl.exe --set-default-version 2 *> $null
        $have = (wsl.exe --list --quiet 2>$null) -join "`n"
        if ($have -match [regex]::Escape($Distro)) {
            Log "WSL: distro $Distro already present"
        } else {
            Log "WSL: installing distro $Distro (no launch)..."
            wsl.exe --install -d $Distro --no-launch | ForEach-Object { if ($_) { Log "  wsl: $_" } }
            Log "WSL: distro install exit code $LASTEXITCODE"
        }
        if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') {
            Log 'WSL: a REBOOT is pending to finish enabling Windows features'
        }
    } catch {
        $script:failed++
        Log "WSL: FAILED - $($_.Exception.Message)"
    }
}

Log "=== admin-setup finished, failed steps: $script:failed ==="
if (-not $NoPause) { Read-Host 'Done. Press Enter to close this window' | Out-Null }
exit $script:failed
