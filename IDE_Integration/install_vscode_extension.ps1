# Install ZAP VSCode Extension
# This script copies the extension to the VSCode extensions directory

$ErrorActionPreference = "Stop"

$extensionSource = "$PSScriptRoot\dushino.zap-language"

# Check if source exists
if (-not (Test-Path $extensionSource)) {
    Write-Host "ERROR: Extension source folder not found at: $extensionSource" -ForegroundColor Red
    exit 1
}

function Install-ZapExtension {
    param (
        [string]$TargetDir,
        [string]$IdeName
    )

    if (-not (Test-Path $TargetDir)) {
        Write-Host "Skipping $IdeName installation: Directory not found at $TargetDir" -ForegroundColor DarkGray
        return
    }

    Write-Host "Installing ZAP Extension for $IdeName..." -ForegroundColor Cyan

    $extensionDest = Join-Path $TargetDir "dushino.zap-language"
    
    # Remove old installations
    $oldPaths = @(
        (Join-Path $TargetDir "dushino42.zap-language"),
        $extensionDest
    )

    foreach ($oldPath in $oldPaths) {
        if (Test-Path $oldPath) {
            Write-Host "Removing old installation: $oldPath" -ForegroundColor Yellow
            Remove-Item $oldPath -Recurse -Force
        }
    }

    # Remove extensions cache file
    $extensionsJson = Join-Path $TargetDir "extensions.json"
    if (Test-Path $extensionsJson) {
        Write-Host "Removing extensions cache: $extensionsJson" -ForegroundColor Yellow
        try {
            Remove-Item $extensionsJson -Force
        }
        catch {
            Write-Host "Warning: failed to remove $extensionsJson - $_" -ForegroundColor Yellow
        }
    }

    # Copy extension
    Write-Host "Copying extension to: $extensionDest" -ForegroundColor Green
    Copy-Item $extensionSource $extensionDest -Recurse
    Write-Host "Extension installed for $IdeName successfully!`n" -ForegroundColor Green
}

# Install for VSCode
Install-ZapExtension -TargetDir "$env:USERPROFILE\.vscode\extensions" -IdeName "VS Code"

# Install for Antigravity
Install-ZapExtension -TargetDir "$env:USERPROFILE\.antigravity\extensions" -IdeName "Antigravity"

Write-Host "Installation process completed." -ForegroundColor Cyan
Write-Host "Please restart your IDEs to activate the extension." -ForegroundColor Cyan

