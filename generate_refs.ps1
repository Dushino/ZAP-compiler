#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Generate .ref files for all tests by running the compiler, assembler, linker, and simulator

.DESCRIPTION
    This script iterates through all test directories, compiles the ZAP code, and generates
    reference output files by running the simulator.
#>

# Configuration
$ZC = "python compiler.py"
$AS = "ca65"
$LD = "ld65"
$DA = "da65"
$SIM = "6502_simulator.exe"
$LIBDIR = "lib"

$ATARI_CPU = "6502"
$ATARI_AS_OPTS = "-I $LIBDIR -t none --cpu $ATARI_CPU -g"

# Check if ca65 is available
$caAvailable = $null -ne (where.exe ca65 2>$null)
if (-not $caAvailable) {
    Write-Host "ERROR: ca65 assembler not found in PATH"
    Write-Host "Cannot generate reference files without the assembler"
    exit 1
}

# Check if simulator is available
$simAvailable = $null -ne (where.exe 6502_simulator.exe 2>$null)
if (-not $simAvailable) {
    Write-Host "ERROR: 6502_simulator.exe not found in PATH"
    Write-Host "Cannot generate reference files without the simulator"
    exit 1
}

# Process all test directories
$testDirs = Get-ChildItem -Path "tests\pass" -Directory
$totalTests = $testDirs.Count
$processedTests = 0
$failedTests = 0

foreach ($testDir in $testDirs) {
    $processedTests++
    Write-Progress -Activity "Generating reference files" -Status $testDir.Name -PercentComplete (($processedTests / $totalTests) * 100)
    
    # Find .zap files in this directory
    $zapFiles = Get-ChildItem -Path $testDir.FullName -Filter "*.zap"
    
    if ($zapFiles.Count -eq 0) {
        continue
    }
    
    foreach ($zapFile in $zapFiles) {
        $baseName = $zapFile.BaseName
        $testDirPath = $testDir.FullName
        $refFile = Join-Path $testDirPath "$baseName.ref"
        
        # Skip if .ref file already exists
        if (Test-Path $refFile) {
            continue
        }
        
        # Test both variants: default and -6502
        $variants = @(
            @{ flags = ""; name = "_default"; cpu = "65c02" },
            @{ flags = "-6502"; name = "_6502"; cpu = "6502" }
        )
        
        foreach ($variant in $variants) {
            $flags = $variant.flags
            $variantName = $variant.name
            $cpu = $variant.cpu
            
            $outputFile = Join-Path $testDirPath "$baseName$variantName.s"
            $objFile = Join-Path $testDirPath "$baseName$variantName.o"
            $exehdrObj = Join-Path $testDirPath "$baseName${variantName}_exehdr.o"
            $binFile = Join-Path $testDirPath "$baseName$variantName.com"
            $cutFile = Join-Path $testDirPath "$baseName$variantName.cut"
            $disFile = Join-Path $testDirPath "$baseName$variantName.dis65"
            $cfgFile = Join-Path $testDirPath "$baseName.json"
            $txtFile = Join-Path $testDirPath "$baseName$variantName.txt"
            
            # Compile ZAP file
            $cmd = if ($flags) { "$ZC $flags `"$($zapFile.FullName)`" -o `"$outputFile`"" } else { "$ZC `"$($zapFile.FullName)`" -o `"$outputFile`"" }
            $output = Invoke-Expression $cmd 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Host "FAIL: Compilation failed for $baseName$variantName"
                $failedTests++
                continue
            }
            
            # Assemble to object
            $cmd = "$AS $ATARI_AS_OPTS `"$outputFile`" -o `"$objFile`""
            Invoke-Expression $cmd 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "FAIL: Assembly failed for $baseName$variantName"
                $failedTests++
                continue
            }
            
            # Assemble Atari header
            $cmd = "$AS $ATARI_AS_OPTS $LIBDIR\atari\exehdr.s -o `"$exehdrObj`""
            Invoke-Expression $cmd 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "FAIL: Assembly of exehdr.s failed for $baseName$variantName"
                $failedTests++
                continue
            }
            
            # Link binary
            $cmd = "$LD -C cfg\my_atari.cfg `"$objFile`" `"$exehdrObj`" -o `"$binFile`""
            Invoke-Expression $cmd 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "FAIL: Linking failed for $baseName$variantName"
                $failedTests++
                continue
            }
            
            # Create cut binary (skip 6-byte header)
            $data = Get-Content -Path $binFile -Encoding Byte -ReadCount 0
            $data[6..($data.Length-1)] | Set-Content -Path $cutFile -Encoding Byte
            
            # Disassemble
            $cmd = "$DA --cpu $cpu --multi-pass --start-addr `$4006 --comments 3 --hexoffs --verbose --verbose `"$cutFile`" > `"$disFile`""
            Invoke-Expression $cmd 2>&1 | Out-Null
            
            # Run simulator
            $cmd = "$SIM --cpu $cpu --config `"$cfgFile`" --verbose --dump-file `"$txtFile`" `"$binFile`""
            Invoke-Expression $cmd 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "FAIL: Simulation failed for $baseName$variantName"
                $failedTests++
                continue
            }
            
            # Copy the first successful variant's output as .ref file
            if (-not (Test-Path $refFile)) {
                Copy-Item $txtFile $refFile
                Write-Host "GENERATED: $baseName.ref from variant $variantName"
            }
        }
    }
}

Write-Progress -Activity "Generating reference files" -Completed

Write-Host ""
Write-Host "=========================================="
Write-Host "Reference file generation complete"
Write-Host "=========================================="
Write-Host "Processed: $processedTests tests"
Write-Host "Failed: $failedTests tests"

if ($failedTests -gt 0) {
    exit 1
} else {
    exit 0
}
