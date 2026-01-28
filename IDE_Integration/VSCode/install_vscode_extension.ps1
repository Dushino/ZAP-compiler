# Install ZAP VSCode Extension
# This script copies the extension to the VSCode extensions directory

$ErrorActionPreference = "Stop"

$extensionSource = "$PSScriptRoot\dushino42.zap-language"
$extensionDest = "$env:USERPROFILE\.vscode\extensions\dushino42.zap-language"

Write-Host "Installing ZAP VSCode Extension..." -ForegroundColor Cyan

# Check if source exists
if (-not (Test-Path $extensionSource)) {
    Write-Host "ERROR: Extension source folder not found at: $extensionSource" -ForegroundColor Red
    exit 1
}

# Remove old installations
$oldPaths = @(
    "$env:USERPROFILE\.vscode\extensions\dushino42.zap-language",
    "$env:USERPROFILE\.vscode\extensions\dushino42.zap-language"
)

foreach ($oldPath in $oldPaths) {
    if (Test-Path $oldPath) {
        Write-Host "Removing old installation: $oldPath" -ForegroundColor Yellow
        Remove-Item $oldPath -Recurse -Force
    }
}

# Copy extension with correct name
Write-Host "Copying extension to: $extensionDest" -ForegroundColor Green
Copy-Item $extensionSource $extensionDest -Recurse

Write-Host "`nExtension installed successfully!" -ForegroundColor Green
Write-Host "Please restart VSCode to activate the extension." -ForegroundColor Cyan

