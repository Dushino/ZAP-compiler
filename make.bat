@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

rem ======================================================================
rem ZAP Compiler Build System for Windows
rem ======================================================================

rem Configuration
set "APPNAME=p1"
set "LIBDIR=lib"
set "SRC1DIR=src1"
set "SRC2DIR=src2"
set "OBJDIR=obj"
set "BINDIR=out"

rem Compiler and assembler tools
set "ZC=python compiler.py"
set "AS=ca65"
set "LD=ld65"
set "DA=da65"
set "SIM=6502_simulator.exe"


rem Paths
set "APPDIR=%APPNAME%"
set "APPSRC1DIR=%APPDIR%\%SRC1DIR%"
set "APPSRC1=%APPSRC1DIR%\%APPNAME%.zap"
set "APPSRC2DIR=%APPDIR%\%SRC2DIR%"
set "APPSRC=%APPSRC2DIR%\%APPNAME%.s"
set "APPOBJDIR=%APPDIR%\%OBJDIR%"
set "APPOBJ=%APPOBJDIR%\%APPNAME%.o"
set "APPBINDIR=%APPDIR%\%BINDIR%"
set "APPBIN=%APPBINDIR%\%APPNAME%"

rem CPU options
set "ATARI_CPU=6502"
set "ATARI_AS_OPTS=-I %LIBDIR% -t none --cpu %ATARI_CPU% -g"
set "SBC_CPU=w65c02"
set "SBC_AS_OPTS=-I %LIBDIR% -t none --cpu %SBC_CPU% -g"
rem Note: -g flag enables debug info generation in object files for VICE/Oricutron debugging


rem ======================================================================
rem Parse command line arguments
rem ======================================================================

if "%1"=="" goto all
if /I "%1"=="all" goto all
if /I "%1"=="atari" goto atari
if /I "%1"=="sbc" goto sbc
if /I "%1"=="run" goto run
if /I "%1"=="tests" goto tests
if /I "%1"=="test" goto tests
if /I "%1"=="clean" goto clean
if /I "%1"=="compile_atari" goto compile_atari
if /I "%1"=="compile_sbc" goto compile_sbc

echo Unknown target: %1
echo.
echo Available targets:
echo   all            - Build Atari binary (default)
echo   atari          - Build Atari binary
echo   sbc            - Build SBC binary
echo   run            - Build and run Atari binary in emulator
echo   tests          - Run full test suite
echo   test [path]    - Test a single directory under tests/ (e.g., "test pass/015-for-loop")
echo   clean          - Clean build artifacts
goto end


rem ======================================================================
rem Target: all (default - builds atari)
rem ======================================================================
:all
goto atari


rem ======================================================================
rem Target: run (builds atari then runs in emulator)
rem ======================================================================
:run
echo.
echo ==========================================
echo Building and running Atari binary...
echo ==========================================
call :atari
if errorlevel 1 goto error
echo.
echo Running in Atari emulator...
atari800 -basic "%APPBIN%.com"
goto end


rem ======================================================================
rem Target: atari
rem ======================================================================
:atari
call :compile_atari
if errorlevel 1 exit /b 1

echo Assembling Atari executable header...
%AS% %ATARI_AS_OPTS% %LIBDIR%\atari\exehdr.s -o %APPOBJDIR%\exehdr.o
if errorlevel 1 exit /b 1

echo Linking Atari binary...
%LD% -C cfg\my_atari.cfg %APPOBJ% %APPOBJDIR%\exehdr.o -o %APPBIN%.com
if errorlevel 1 exit /b 1

echo Creating cut binary (skipping header)...
powershell -Command "$data = Get-Content -Path '%APPBIN%.com' -Encoding Byte -ReadCount 0; $data[6..$($data.Length-1)] | Set-Content -Path '%APPBIN%.cut' -Encoding Byte"
if errorlevel 1 exit /b 1

echo Disassembling binary...
%DA% --cpu %ATARI_CPU% --multi-pass -i cfg/my_atari.info  --comments 3 --hexoffs --verbose --verbose %APPBIN%.cut > %APPBIN%.da65
if errorlevel 1 exit /b 1

echo.
echo ✓ Atari build complete: %APPBIN%.com
exit /b 0


rem ======================================================================
rem Target: compile_atari
rem ======================================================================
:compile_atari
echo Creating directories...
if not exist "%APPSRC2DIR%" mkdir "%APPSRC2DIR%"
if not exist "%APPOBJDIR%" mkdir "%APPOBJDIR%"
if not exist "%APPBINDIR%" mkdir "%APPBINDIR%"

echo Compiling ZAP source to assembly...
%ZC% -6502 %APPSRC1% -o %APPSRC%
if errorlevel 1 exit /b 1

echo Assembling to object file...
%AS% %ATARI_AS_OPTS% %APPSRC% -o %APPOBJ%
if errorlevel 1 exit /b 1

exit /b 0


rem ======================================================================
rem Target: sbc
rem ======================================================================
:sbc
call :compile_sbc
if errorlevel 1 exit /b 1

echo Assembling SBC executable header...
%AS% %SBC_AS_OPTS% %LIBDIR%\atari\exehdr.s -o %APPOBJDIR%\exehdr.o
if errorlevel 1 exit /b 1

echo Linking SBC binary...
%LD% -C cfg\my_sbc.cfg %APPOBJ% -o %APPBIN%.com
if errorlevel 1 exit /b 1

echo Disassembling binary...
%DA% --cpu %SBC_CPU% --multi-pass -i cfg/my_atari.info  --comments 3 --hexoffs --verbose --verbose %APPBIN%.cut > %APPBIN%.da65
if errorlevel 1 exit /b 1

echo.
echo ✓ SBC build complete: %APPBIN%.com
exit /b 0


rem ======================================================================
rem Target: compile_sbc
rem ======================================================================
:compile_sbc
echo Creating directories...
if not exist "%APPSRC2DIR%" mkdir "%APPSRC2DIR%"
if not exist "%APPOBJDIR%" mkdir "%APPOBJDIR%"
if not exist "%APPBINDIR%" mkdir "%APPBINDIR%"

echo Compiling ZAP source to assembly...
%ZC% %APPSRC1% -o %APPSRC%
if errorlevel 1 exit /b 1

echo Assembling to object file...
%AS% %SBC_AS_OPTS% %APPSRC% -o %APPOBJ%
if errorlevel 1 exit /b 1

exit /b 0


rem ======================================================================
rem Target: tests
rem ======================================================================
:tests
echo.
echo ==========================================
echo Running ZAP Compiler Test Suite
echo ==========================================
echo.

rem Determine test directories
if not "%2"=="" (
    rem Single test directory mode
    set "TEST_DIR=%2"
    rem Normalize path: remove leading ./ or .\
    if "!TEST_DIR:~0,2!"==".\" set "TEST_DIR=!TEST_DIR:~2!"
    if "!TEST_DIR:~0,2!"=="./" set "TEST_DIR=!TEST_DIR:~2!"
    rem Ensure path uses backslashes
    set "TEST_DIR=!TEST_DIR:/=\!"
    
    rem Check if directory exists
    if not exist "!TEST_DIR!" (
        echo Error: Test directory not found: !TEST_DIR!
        echo.
        echo Usage: make test [path]
        echo   e.g. make test pass/015-for-loop
        exit /b 1
    )
    set "PASS_DIRS=!TEST_DIR!"
    set "FAIL_DIRS="
    echo Testing single directory: !TEST_DIR!
    echo.
) else (
    rem Full test suite mode
    set "PASS_DIRS=tests\pass"
    set "FAIL_DIRS=tests\fail"
)

rem Check if ca65 is available
where ca65 >nul 2>&1
if !errorlevel! neq 0 (
    echo WARNING: ca65 assembler not found in PATH
    echo The tests will only check if ZAP compilation succeeds, not assembly
    echo To run full tests, install cc65 toolchain and add it to PATH
    echo.
    set "AS_AVAILABLE=0"
) else (
    set "AS_AVAILABLE=1"
)

if not exist "tests\pass" mkdir "tests\pass"
if not exist "tests\fail" mkdir "tests\fail"

set "pass_count=0"
set "fail_count=0"
set "error_count=0"

echo Testing files that SHOULD PASS...
echo ------------------------------------------

if exist "tests.txt" del /Q "tests.txt" 2>nul

if not "%2"=="" (
    rem Single directory mode - use non-recursive for loop
    for %%f in ("!PASS_DIRS!\*.zap") do (
    set "base=%%~nf"
    set "fullname=%%~nxf"
    
    rem Skip .zaplib files (library files, not test programs)
    if not "!fullname:zaplib=!"=="!fullname!" (
        rem Skip this file - it's a .zaplib file
    ) else (
        set "variant_pass=0"
        set "variant_fail=0"
        set "testdir=!PASS_DIRS!"

    rem Test all variants: default, -6502
    for %%v in (0 1) do (
        if %%v equ 0 (
            set "variant_flags="
            set "variant_name=_default"
        ) else (
            set "variant_flags=-6502"
            set "variant_name=_6502"
        )
        set "output_file=!testdir!\!base!!variant_name!.s"
        set "obj_file=!testdir!\!base!!variant_name!.o"
        
        rem Determine CPU type
        set "as_cpu=65c02"
        echo !variant_flags! | findstr /C:"-6502" >nul 2>&1
        if !errorlevel! equ 0 set "as_cpu=6502"
        
        echo %%f >> tests.txt

        rem Compile ZAP file
        if "!variant_flags!"=="" (
            echo %ZC% "%%f" -o "!output_file!" >> tests.txt
            %ZC% "%%f" -o "!output_file!" >nul 2>&1
        ) else (
            echo %ZC% !variant_flags! "%%f" -o "!output_file!" >> tests.txt
            %ZC% !variant_flags! "%%f" -o "!output_file!" >nul 2>&1 >> tests.txt
        )
        
        if !errorlevel! equ 0 (
            rem Assemble to object (only if assembler is available)
            if !AS_AVAILABLE! equ 1 (
                echo %AS% -I %LIBDIR% -t none --cpu !as_cpu! -g "!output_file!" -o "!obj_file!" >> tests.txt
                     %AS% -I %LIBDIR% -t none --cpu !as_cpu! -g "!output_file!" -o "!obj_file!" >> tests.txt
                if !errorlevel! equ 0 (
                    rem Create Atari binary with header
                    set "exehdr_obj=!testdir!\!base!!variant_name!_exehdr.o"
                    set "autostart_obj=!testdir!\!base!!variant_name!_autostart.o"
                    set "bin_file=!testdir!\!base!!variant_name!.com"
                    echo %AS% -I %LIBDIR% -t none --cpu !as_cpu! -g %LIBDIR%\atari\autostart.s -o "!autostart_obj!" >> tests.txt
                         %AS% -I %LIBDIR% -t none --cpu !as_cpu! -g %LIBDIR%\atari\autostart.s -o "!autostart_obj!" >> tests.txt
                    %AS% -I %LIBDIR% -t none --cpu !as_cpu! -g %LIBDIR%\atari\exehdr.s -o "!exehdr_obj!"
                    if !errorlevel! equ 0 (
                        %LD% -C cfg\my_atari.cfg  -o "!bin_file!" "!exehdr_obj!" "!obj_file!"  "!autostart_obj!"
                        if !errorlevel! equ 0 (
                            rem Create cut binary (skip 6-byte header) for disassembly
                            set "cut_file=!testdir!\!base!!variant_name!.cut"
                            set "dis_file=!testdir!\!base!!variant_name!.da65"
                            set "cfg_file=!testdir!\!base!.json"
                            powershell -Command "$data = Get-Content -Path '!bin_file!' -Encoding Byte -ReadCount 0; $data[6..$($data.Length-1)] | Set-Content -Path '!cut_file!' -Encoding Byte" >nul 2>&1
                            echo %DA% --cpu !as_cpu! --multi-pass -i cfg/my_atari.info --comments 3 --hexoffs --verbose --verbose "!cut_file!" >> tests.txt
                                 %DA% --cpu !as_cpu! --multi-pass -i cfg/my_atari.info  --comments 3 --hexoffs --verbose --verbose "!cut_file!" > "!dis_file!" 
                            set "txt_file=!testdir!\!base!!variant_name!.txt"
                            echo %SIM% --cpu !as_cpu! --config !cfg_file! --verbose --dump-file "!txt_file!" "!bin_file!" >> tests.txt
                                 %SIM% --cpu !as_cpu! --config !cfg_file! --verbose --dump-file "!txt_file!" "!bin_file!" >> tests.txt
                            if !errorlevel! equ 0 (
                                set "ref_file=!testdir!\!base!.ref"
                                rem check result by comparing with reference file
                                echo fc "!ref_file!" "!txt_file!" >> tests.txt
                                fc "!ref_file!" "!txt_file!" 2>nul > nul
                                if !errorlevel! equ 0 (
                                    set /a variant_pass+=1
                                ) else (
                                    set /a variant_fail+=1
                                    echo Simulation result does not match reference >> tests.txt
                                    echo ❌ Simulation result does not match reference
                                )                                
                            ) else (
                                set /a variant_fail+=1
                                echo Simulation failed >> tests.txt
                                echo ❌ Simulation failed
                            )
                        ) else (
                            set /a variant_fail+=1
                            echo Linker failed >> tests.txt
                            echo ❌ Linker failed                            
                        )
                    ) else (
                        set /a variant_fail+=1
                        echo Assemler failed on %LIBDIR%\atari\exehdr.s  >> tests.txt
                        echo ❌ Assemler failed on %LIBDIR%\atari\exehdr.s 

                    )
                ) else (
                    set /a variant_fail+=1
                    echo Assembler failed on "!output_file!" >> tests.txt
                    echo ❌ Assembler failed on "!output_file!"
                )
            ) else (
                rem Just count compilation success
                set /a variant_fail+=1
                echo ca65 not found, compilation failed.
            )
        ) else (
            set /a variant_fail+=1
            echo ZAP compiler failed >> tests.txt
            echo ❌ ZAP compiler failed
        )
        echo:  >> tests.txt
        echo:  >> tests.txt
        echo --------------------------------------------------------------- >> tests.txt                
    )
    
    rem Output result for this test
    set "result_msg=!base!.zap: "
    set "spaces=                              "
    set "padded_msg=!result_msg!!spaces!"
    set "padded_msg=!padded_msg:~0,30!"
    
    if !variant_fail! equ 0 (
        echo !padded_msg!PASS ^(all 2 variants^)
        set /a pass_count+=1
    ) else (
        echo !padded_msg!FAIL ^(!variant_fail!/2 variants failed^)
        set /a error_count+=1
    )
    )
    )
) else (
    rem Full recursive directory mode
    for /R "tests\pass" %%f in (*.zap) do (
    set "base=%%~nf"
    set "fullname=%%~nxf"
    
    rem Skip .zaplib files (library files, not test programs)
    if not "!fullname:zaplib=!"=="!fullname!" (
        rem Skip this file - it's a .zaplib file
    ) else (
        set "variant_pass=0"
        set "variant_fail=0"
        set "testdir=%%~dpf"
        set "testdir=!testdir:~0,-1!"

    rem Test all variants: default, -6502
    for %%v in (0 1) do (
        if %%v equ 0 (
            set "variant_flags="
            set "variant_name=_default"
        ) else (
            set "variant_flags=-6502"
            set "variant_name=_6502"
        )
        set "output_file=!testdir!\!base!!variant_name!.s"
        set "obj_file=!testdir!\!base!!variant_name!.o"
        
        rem Determine CPU type
        set "as_cpu=65c02"
        echo !variant_flags! | findstr /C:"-6502" >nul 2>&1
        if !errorlevel! equ 0 set "as_cpu=6502"
        
        echo %%f >> tests.txt

        rem Compile ZAP file
        if "!variant_flags!"=="" (
            echo %ZC% "%%f" -o "!output_file!" >> tests.txt
            %ZC% "%%f" -o "!output_file!" >nul 2>&1
        ) else (
            echo %ZC% !variant_flags! "%%f" -o "!output_file!" >> tests.txt
            %ZC% !variant_flags! "%%f" -o "!output_file!" >nul 2>&1 >> tests.txt
        )
        
        if !errorlevel! equ 0 (
            rem Assemble to object (only if assembler is available)
            if !AS_AVAILABLE! equ 1 (
                echo %AS% -I %LIBDIR% -t none --cpu !as_cpu! -g "!output_file!" -o "!obj_file!" >> tests.txt
                %AS% -I %LIBDIR% -t none --cpu !as_cpu! -g "!output_file!" -o "!obj_file!" >nul 2>&1 >> tests.txt
                if !errorlevel! equ 0 (
                    rem Create Atari binary with header
                    set "exehdr_obj=!testdir!\!base!!variant_name!_exehdr.o"
                    set "bin_file=!testdir!\!base!!variant_name!.com"
                    echo %AS% -I %LIBDIR% -t none --cpu !as_cpu! -g %LIBDIR%\atari\exehdr.s -o "!exehdr_obj!" >> tests.txt
                    %AS% -I %LIBDIR% -t none --cpu !as_cpu! -g %LIBDIR%\atari\exehdr.s -o "!exehdr_obj!" >nul 2>&1
                    if !errorlevel! equ 0 (
                        echo %LD% -C cfg\my_atari.cfg "!obj_file!" "!exehdr_obj!" -o "!bin_file!" >> tests.txt
                        %LD% -C cfg\my_atari.cfg "!obj_file!" "!exehdr_obj!" -o "!bin_file!" >nul 2>&1
                        if !errorlevel! equ 0 (
                            rem Create cut binary (skip 6-byte header) for disassembly
                            set "cut_file=!testdir!\!base!!variant_name!.cut"
                            set "dis_file=!testdir!\!base!!variant_name!.da65"
                            set "cfg_file=!testdir!\!base!.json"
                            powershell -Command "$data = Get-Content -Path '!bin_file!' -Encoding Byte -ReadCount 0; $data[6..$($data.Length-1)] | Set-Content -Path '!cut_file!' -Encoding Byte" >nul 2>&1
                            echo %DA% --cpu !as_cpu! --multi-pass -i cfg/my_atari.info  --comments 3 --hexoffs --verbose --verbose "!cut_file!" >> tests.txt
                            %DA% --cpu !as_cpu! --multi-pass -i cfg/my_atari.info  --comments 3 --hexoffs --verbose --verbose "!cut_file!" > "!dis_file!" 2>nul
                            set "txt_file=!testdir!\!base!!variant_name!.txt"
                            echo %SIM% --cpu !as_cpu! --config !cfg_file! --verbose --dump-file "!txt_file!" "!bin_file!" >> tests.txt
                            %SIM% --cpu !as_cpu! --config !cfg_file! --verbose --dump-file "!txt_file!" "!bin_file!" >> tests.txt
                            if !errorlevel! equ 0 (
                                set "ref_file=!testdir!\!base!.ref"
                                rem check result by comparing with reference file
                                echo fc "!ref_file!" "!txt_file!" >> tests.txt
                                fc "!ref_file!" "!txt_file!" 2>nul > nul
                                if !errorlevel! equ 0 (
                                    set /a variant_pass+=1
                                ) else (
                                    set /a variant_fail+=1
                                    echo Simulation result does not match reference >> tests.txt
                                    echo  ❌ Simulation result does not match reference
                                )                                
                            ) else (
                                set /a variant_fail+=1
                                echo  Simulation failed >> tests.txt
                                echo  ❌ Simulation failed >> tests.txt
                            )
                        ) else (
                            set /a variant_fail+=1
                            echo  Linker failed >> tests.txt
                            echo  ❌ Linker failed
                        )
                    ) else (
                        set /a variant_fail+=1
                        echo Assemler failed on %LIBDIR%\atari\exehdr.s  >> tests.txt
                        echo  ❌ Assemler failed on %LIBDIR%\atari\exehdr.s
                    )
                ) else (
                    set /a variant_fail+=1
                    echo Assembler failed on "!output_file!" >> tests.txt
                    echo ❌ Assembler failed on "!output_file!"

                )
            ) else (
                rem Just count compilation success
                set /a variant_fail+=1
                echo ca65 not found, compilation failed.
            )
        ) else (
            set /a variant_fail+=1
            echo ZAP compiler failed >> tests.txt
            echo ❌  ZAP compiler failed
        )
        echo:  >> tests.txt
        echo:  >> tests.txt
        echo --------------------------------------------------------------- >> tests.txt        
    )
    
    rem Output result for this test
    set "result_msg=!base!.zap: "
    set "spaces=                              "
    set "padded_msg=!result_msg!!spaces!"
    set "padded_msg=!padded_msg:~0,30!"
    
    if !variant_fail! equ 0 (
        echo !padded_msg!✅ PASS ^(all 2 variants^)
        set /a pass_count+=1
    ) else (
        echo !padded_msg!❌ FAIL ^(!variant_fail!/2 variants failed^)
        set /a error_count+=1
    )
    )
    )
)

rem Only test FAIL directory if running full test suite
if "%2"=="" (
    echo.
    echo Testing files that SHOULD FAIL...
    echo ------------------------------------------

    for /R "tests\fail" %%f in (*.zap) do (
        set "base=%%~nf"
        set "testdir=%%~dpf"
        set "testdir=!testdir:~0,-1!"
        set "result_msg=!base!.zap: "
        set "spaces=                              "
        set "padded_msg=!result_msg!!spaces!"
        set "padded_msg=!padded_msg:~0,30!"
        
        %ZC% -6502 "%%f" -o "!testdir!\!base!.s" >nul 2>&1
        if !errorlevel! equ 0 (
            echo !padded_msg!✗ ^(expected to fail but passed^)
            set /a error_count+=1
        ) else (
            echo !padded_msg!✓ PASS ^(correctly rejected^)
            set /a fail_count+=1
        )
    )
)

echo.
echo ==========================================
echo Test Results Summary
echo ==========================================
echo Should-pass tests: !pass_count! passed
echo Should-fail tests: !fail_count! correctly rejected
echo Errors: !error_count!
echo.

if !error_count! equ 0 (
    echo All tests behaved as expected!
    exit /b 0
) else (
    echo !error_count! test^(s^) behaved incorrectly
    exit /b 1
)


rem ======================================================================
rem Target: clean
rem ======================================================================
:clean
echo Cleaning build artifacts...

if exist "%APPOBJDIR%\*.o" del /Q "%APPOBJDIR%\*.o" 2>nul
if exist "%APPBINDIR%\*.com" del /Q "%APPBINDIR%\*.com" 2>nul
if exist "%APPBINDIR%\*.cut" del /Q "%APPBINDIR%\*.cut" 2>nul
if exist "%APPBINDIR%\*.da65" del /Q "%APPBINDIR%\*.da65" 2>nul
if exist "%APPSRC2DIR%\*.s" del /Q "%APPSRC2DIR%\*.s" 2>nul
if exist "%APPSRC2DIR%\*.inc" del /Q "%APPSRC2DIR%\*.inc" 2>nul

rem Clean test artifacts recursively in subdirectories
for /R "tests\pass" %%f in (*.s) do del /Q "%%f" 2>nul
for /R "tests\pass" %%f in (*.o) do del /Q "%%f" 2>nul
for /R "tests\pass" %%f in (*.com) do del /Q "%%f" 2>nul
for /R "tests\pass" %%f in (*.txt) do del /Q "%%f" 2>nul
for /R "tests\pass" %%f in (*.cut) do del /Q "%%f" 2>nul
for /R "tests\pass" %%f in (*.da65) do del /Q "%%f" 2>nul
for /R "tests\fail" %%f in (*.s) do del /Q "%%f" 2>nul
for /R "tests\fail" %%f in (*.o) do del /Q "%%f" 2>nul

echo Clean complete
goto end


rem ======================================================================
rem Error handler
rem ======================================================================
:error
echo.
echo Build failed!
exit /b 1


rem ======================================================================
rem End
rem ======================================================================
:end
endlocal
