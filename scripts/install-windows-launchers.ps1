$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir "..")).Path
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Configo Workspace"

New-Item -ItemType Directory -Force -Path $startMenu | Out-Null

$wsh = New-Object -ComObject WScript.Shell

$launchers = @(
  @{
    Name = "Configo Claude Workspace"
    Script = Join-Path $root "scripts\claude-workspace.bat"
    Description = "Launch Claude with the shared Configo workspace runtime"
    Icon = "$env:SystemRoot\System32\shell32.dll,70"
  },
  @{
    Name = "Configo OpenCode Workspace"
    Script = Join-Path $root "scripts\opencode-workspace.bat"
    Description = "Launch OpenCode with the shared Configo workspace runtime"
    Icon = "$env:SystemRoot\System32\shell32.dll,137"
  },
  @{
    Name = "Configo Cross Resume"
    Script = Join-Path $root "scripts\cross-resume.bat"
    Description = "List and resume shared Configo workspace conversations"
    Icon = "$env:SystemRoot\System32\shell32.dll,44"
  }
)

foreach ($launcher in $launchers) {
  foreach ($baseDir in @($desktop, $startMenu)) {
    $shortcutPath = Join-Path $baseDir ($launcher.Name + ".lnk")
    $shortcut = $wsh.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $launcher.Script
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = $launcher.Description
    $shortcut.IconLocation = $launcher.Icon
    $shortcut.Save()
  }
}

Write-Host "Installed desktop and Start Menu launchers:"
foreach ($launcher in $launchers) {
  Write-Host " - $($launcher.Name)"
}
