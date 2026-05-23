# yato_visibility_kit dev uninstall: Junction を剥がす

[CmdletBinding()]
param(
    [string]$BlenderVersion = ""
)

$ErrorActionPreference = "Stop"

$blenderUserRoot = Join-Path $env:APPDATA "Blender Foundation\Blender"

if ([string]::IsNullOrWhiteSpace($BlenderVersion)) {
    $candidates = Get-ChildItem -Path $blenderUserRoot -Directory |
        Where-Object { $_.Name -match '^\d+\.\d+$' }
    $scored = $candidates | ForEach-Object {
        $userpref = Join-Path $_.FullName "config\userpref.blend"
        $mtime = if (Test-Path $userpref) { (Get-Item $userpref).LastWriteTime } else { [DateTime]::MinValue }
        [PSCustomObject]@{ Name = $_.Name; MTime = $mtime }
    } | Sort-Object MTime -Descending
    $BlenderVersion = $scored[0].Name
}

$target = Join-Path $blenderUserRoot "$BlenderVersion\extensions\user_default\yato_visibility_kit"
if (-not (Test-Path $target)) {
    Write-Host "[info] 何もありません: $target"
    exit 0
}
$item = Get-Item $target -Force
if ($item.LinkType -eq "Junction") {
    & cmd /c rmdir "`"$target`""
    Write-Host "[done] Junction を剥がしました: $target"
} else {
    Write-Host "[warn] Junction ではありません: $target"
    Write-Host "       実フォルダの可能性があります。手動で確認してください。"
}
