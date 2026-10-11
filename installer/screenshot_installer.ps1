<#
Runs the real Blaze installer in a visible desktop session, one wizard page at a time, and photographs each page.

  pwsh installer/screenshot_installer.ps1 -Setup dist\Blaze_Setup_0.2.0.exe -OutDir screens\installer -InstallDir $env:RUNNER_TEMP\BlazeShots

Best effort by design: it needs an interactive desktop (GitHub's Windows runners have one) and presses keys to move through
the pages. Whatever was captured before a problem is kept, and the manifest says which pages are missing.
Writes <OutDir>\*.png and <OutDir>\manifest.json.
#>
param(
  [Parameter(Mandatory = $true)][string]$Setup,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [Parameter(Mandatory = $true)][string]$InstallDir
)
$ErrorActionPreference = "Continue"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); }
"@
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$script:manifest = @()

function Snap([string]$name, [string]$title, [string]$check) {
  try {
    $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
    $bmp.Save((Join-Path $OutDir "$name.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    $script:manifest += [pscustomobject]@{ file = "$name.png"; title = $title; check = $check }
    Write-Host "  ok  $name"
  } catch {
    $script:manifest += [pscustomobject]@{ file = ""; title = $title; check = $check; error = $_.Exception.Message }
    Write-Host "  FAIL $name : $($_.Exception.Message)"
  }
}

function SetupWindow { Get-Process | Where-Object { $_.MainWindowTitle -match "^Setup - Blaze" } | Select-Object -First 1 }

function Press([string]$keys) {
  $w = SetupWindow
  if ($w) { [Win]::SetForegroundWindow($w.MainWindowHandle) | Out-Null }
  Start-Sleep -Milliseconds 500
  [System.Windows.Forms.SendKeys]::SendWait($keys)
  Start-Sleep -Seconds 2
}

# /CURRENTUSER skips the "for all users or just me" question, so the pages below are always the same
$null = Start-Process -FilePath $Setup -ArgumentList @("/CURRENTUSER", "/DIR=`"$InstallDir`"", "/LOG=`"$(Join-Path $OutDir 'setup.log')`"")

$deadline = (Get-Date).AddSeconds(90)
while (-not (SetupWindow) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
if (-not (SetupWindow)) {
  Snap "00-no-window" "The installer did not show a window" "The installer should open a window titled Setup - Blaze."
} else {
  Start-Sleep -Seconds 2
  Snap "01-welcome" "Welcome" "The dark Blaze picture on the left, the welcome text mentions it works offline and that everything is included."
  Press "{ENTER}"
  Snap "02-license" "License" "The license text (the Islamic Open Source License) reads as plain text with no stray marks. Next is disabled until you accept."
  Press "%a"
  Snap "03-license-accepted" "License accepted" "I accept the agreement is selected and Next is enabled."
  Press "{ENTER}"
  Snap "04-destination" "Choose where to install" "A folder is suggested; the disk space needed is shown. No admin prompt appeared."
  Press "{ENTER}"
  Snap "05-tasks" "Additional tasks" "Create a desktop shortcut is offered."
  Press "{ENTER}"
  Snap "06-ready" "Ready to install" "A summary of the choices; Install is the default button."
  Press "{ENTER}"
  Start-Sleep -Seconds 6
  Snap "07-installing" "Installing" "A progress bar moves; the small Blaze picture is at the top right."
  $pythonw = Join-Path $InstallDir "runtime\python\pythonw.exe"
  $uninst = Join-Path $InstallDir "unins000.exe"
  $deadline = (Get-Date).AddMinutes(15)
  while (-not (Test-Path $uninst) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 3 }
  Start-Sleep -Seconds 5
  Snap "08-finished" "Finished" "Blaze is ready; Launch Blaze is ticked; the text says where videos are saved."
  Press "{ENTER}"
  Start-Sleep -Seconds 10
  Snap "09-app-started" "After Finish: the app starts" "Blaze opens in your browser (a window or tab may be in front of this screen)."
  Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$InstallDir*" } | Stop-Process -Force -ErrorAction SilentlyContinue
}
ConvertTo-Json -InputObject @($script:manifest) -Depth 4 | Set-Content -Path (Join-Path $OutDir "manifest.json") -Encoding UTF8
Write-Host "installed: $(Test-Path (Join-Path $InstallDir 'runtime\python\pythonw.exe'))"
exit 0
