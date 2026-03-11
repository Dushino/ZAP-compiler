@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

set "spaces=                                                  "

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
python -c "d=open(r'%APPBIN%.com','rb').read();open(r'%APPBIN%.cut','wb').write(d[6:])"
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

rem Pre-assemble exehdr.o for both CPU types (avoids ~610 redundant ca65 calls)
if !AS_AVAILABLE! equ 1 (
    set "CACHED_EXEHDR_6502=%TEMP%\zap_test_exehdr_6502.o"
    set "CACHED_EXEHDR_65C02=%TEMP%\zap_test_exehdr_65c02.o"
    %AS% -I %LIBDIR% -t none --cpu 6502 -g %LIBDIR%\atari\exehdr.s -o "!CACHED_EXEHDR_6502!"
    %AS% -I %LIBDIR% -t none --cpu 65c02 -g %LIBDIR%\atari\exehdr.s -o "!CACHED_EXEHDR_65C02!"
)

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

    rem Test all variants: default, -6502, -O1, -6502 -O1
    for %%v in (0 1 2 3) do (
        if %%v equ 0 (
            set "variant_flags="
            set "variant_name=_default"
        ) else if %%v equ 1 (
            set "variant_flags=-6502"
            set "variant_name=_6502"
        ) else if %%v equ 2 (
            set "variant_flags=-O1"
            set "variant_name=_O1"
        ) else (
            set "variant_flags=-6502 -O1"
            set "variant_name=_6502_O1"
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
                    rem Use cached exehdr.o instead of reassembling
                    if "!as_cpu!"=="6502" (
                        copy /Y "!CACHED_EXEHDR_6502!" "!exehdr_obj!" >nul
                    ) else (
                        copy /Y "!CACHED_EXEHDR_65C02!" "!exehdr_obj!" >nul
                    )
                    if !errorlevel! equ 0 (
                        %LD% -C cfg\my_atari.cfg  -o "!bin_file!" "!exehdr_obj!" "!obj_file!"  "!autostart_obj!"
                        if !errorlevel! equ 0 (
                            set "cfg_file=!testdir!\!base!.json"
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
                                    echo ❌ FAIL: Simulation result does not match reference >> tests.txt
                                    echo ❌ Simulation result does not match reference
                                )                                
                            ) else (
                                set /a variant_fail+=1
                                echo ❌ FAIL: Simulation failed >> tests.txt
                                echo ❌ Simulation failed
                            )
                        ) else (
                            set /a variant_fail+=1
                            echo ❌ FAIL: Linker failed >> tests.txt
                            echo ❌ Linker failed                            
                        )
                    ) else (
                        set /a variant_fail+=1
                        echo ❌ FAIL: Failed to copy cached exehdr.o >> tests.txt
                        echo ❌ Failed to copy cached exehdr.o
                    )
                ) else (
                    set /a variant_fail+=1
                    echo ❌ FAIL: Assembler failed on "!output_file!" >> tests.txt
                    echo ❌ Assembler failed on "!output_file!"
                )
            ) else (
                rem Just count compilation success
                set /a variant_fail+=1
                echo ❌ FAIL: ca65 not found, compilation failed.
            )
        ) else (
            set /a variant_fail+=1
            echo ❌ FAIL: ZAP compiler failed >> tests.txt
            echo ❌ ZAP compiler failed
        )
        echo:  >> tests.txt
        echo:  >> tests.txt
        echo --------------------------------------------------------------- >> tests.txt                
    )
    
    rem Output result for this test
    set "result_msg=!base!.zap: "    
    set "padded_msg=!result_msg!!spaces!"
    set "padded_msg=!padded_msg:~0,40!"
    
    if !variant_fail! equ 0 (
        echo !padded_msg!✅ PASS ^(all 4 variants^)
        set /a pass_count+=1
    ) else (
        echo !padded_msg!❌ FAIL ^(!variant_fail!/4 variants failed^)
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

    rem Test all variants: default, -6502, -O1, -6502 -O1
    for %%v in (0 1 2 3) do (
        if %%v equ 0 (
            set "variant_flags="
            set "variant_name=_default"
        ) else if %%v equ 1 (
            set "variant_flags=-6502"
            set "variant_name=_6502"
        ) else if %%v equ 2 (
            set "variant_flags=-O1"
            set "variant_name=_O1"
        ) else (
            set "variant_flags=-6502 -O1"
            set "variant_name=_6502_O1"
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
                    rem Use cached exehdr.o instead of reassembling
                    if "!as_cpu!"=="6502" (
                        copy /Y "!CACHED_EXEHDR_6502!" "!exehdr_obj!" >nul
                    ) else (
                        copy /Y "!CACHED_EXEHDR_65C02!" "!exehdr_obj!" >nul
                    )
                    if !errorlevel! equ 0 (
                        echo %LD% -C cfg\my_atari.cfg "!obj_file!" "!exehdr_obj!" -o "!bin_file!" >> tests.txt
                        %LD% -C cfg\my_atari.cfg "!obj_file!" "!exehdr_obj!" -o "!bin_file!" >nul 2>&1
                        if !errorlevel! equ 0 (
                            set "cfg_file=!testdir!\!base!.json"
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
                                    echo ❌ FAIL: Simulation result does not match reference >> tests.txt
                                    echo  ❌ Simulation result does not match reference
                                )                                
                            ) else (
                                set /a variant_fail+=1
                                echo  ❌ FAIL: Simulation failed >> tests.txt
                                echo  ❌ Simulation failed >> tests.txt
                            )
                        ) else (
                            set /a variant_fail+=1
                            echo  ❌ FAIL: Linker failed >> tests.txt
                            echo  ❌ Linker failed
                        )
                    ) else (
                        set /a variant_fail+=1
                        echo ❌ FAIL: Failed to copy cached exehdr.o >> tests.txt
                        echo ❌ Failed to copy cached exehdr.o
                    )
                ) else (
                    set /a variant_fail+=1
                    echo ❌ FAIL: Assembler failed on "!output_file!" >> tests.txt
                    echo ❌ Assembler failed on "!output_file!"
                )
            ) else (
                rem Just count compilation success
                set /a variant_fail+=1
                echo ❌ FAIL: ca65 not found, compilation failed. >> tests.txt
                echo ❌ ca65 not found, compilation failed.
            )
        ) else (
            set /a variant_fail+=1
            echo ❌ FAIL: ZAP compiler failed >> tests.txt
            echo ❌ ZAP compiler failed
        )
        echo:  >> tests.txt
        echo:  >> tests.txt
        echo --------------------------------------------------------------- >> tests.txt        
    )
    
    rem Output result for this test
    set "result_msg=!base!.zap: "
    set "padded_msg=!result_msg!!spaces!"
    set "padded_msg=!padded_msg:~0,40!"
    
    if !variant_fail! equ 0 (
        echo !padded_msg!✅ PASS ^(all 4 variants^)
        set /a pass_count+=1
    ) else (
        echo !padded_msg!❌ FAIL ^(!variant_fail!/4 variants failed^)
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

    set "fail_msg_ok=0"
    set "fail_msg_bad=0"
    set "fail_no_err=0"

    for /R "tests\fail" %%f in (*.zap) do (
        set "base=%%~nf"
        set "testdir=%%~dpf"
        set "testdir=!testdir:~0,-1!"
        set "result_msg=!base!.zap: "
        set "padded_msg=!result_msg!!spaces!"
        set "padded_msg=!padded_msg:~0,40!"
        set "err_file=!testdir!\!base!.err"
        set "actual_err_file=!testdir!\!base!_actual.err"

        set "variant_fail=0"
        set "err_checked=0"
        set "err_match=1"
        for %%v in (0 1 2 3) do (
            if %%v equ 0 (
                set "variant_flags="
                set "variant_name=_default"
            ) else if %%v equ 1 (
                set "variant_flags=-6502"
                set "variant_name=_6502"
            ) else if %%v equ 2 (
                set "variant_flags=-O1"
                set "variant_name=_O1"
            ) else (
                set "variant_flags=-6502 -O1"
                set "variant_name=_6502_O1"
            )
            %ZC% !variant_flags! "%%f" -o "!testdir!\!base!!variant_name!.s" >"!actual_err_file!" 2>&1
            if !errorlevel! equ 0 (
                set /a variant_fail+=1
            ) else (
                rem Check error message on first rejected variant
                if !err_checked! equ 0 (
                    if exist "!err_file!" (
                        set "err_checked=1"
                        rem Strip path prefix from actual error: everything up to .zap: followed by digit
                        rem Use python for reliable cross-platform path stripping
                        python -c "import re,sys; actual=open(sys.argv[1],encoding='utf-8',errors='replace').read().strip(); expected=open(sys.argv[2],encoding='utf-8',errors='replace').read().strip(); actual_stripped=re.sub(r'^.*\.zap:(?=\d)','',actual); sys.exit(0 if actual_stripped[:len(expected)]==expected else 1)" "!actual_err_file!" "!err_file!"
                        if !errorlevel! neq 0 (
                            set "err_match=0"
                        )
                    )
                )
            )
        )
        rem Clean up temp file
        if exist "!actual_err_file!" del /Q "!actual_err_file!" 2>nul

        if !variant_fail! neq 0 (
            echo !padded_msg!❌ FAIL: ^(!variant_fail!/4 variants passed^)
            set /a error_count+=1
        ) else if !err_match! equ 0 (
            echo !padded_msg!❌ FAIL: ^(wrong error message^)
            rem Show expected vs actual
            if exist "!err_file!" (
                for /F "usebackq delims=" %%e in ("!err_file!") do echo   Expected: %%e
            )
            set /a fail_msg_bad+=1
            set /a error_count+=1
        ) else (
            if exist "!err_file!" (
                echo !padded_msg!✅ PASS ^(correctly rejected, error message verified^)
                set /a fail_msg_ok+=1
            ) else (
                echo !padded_msg!✅ PASS ^(correctly rejected, no .err reference^)
                set /a fail_no_err+=1
            )
            set /a fail_count+=1
        )
    )
)

echo.
echo ==========================================
echo Test Results Summary
echo ==========================================
echo Should-pass tests: !pass_count! passed
echo Should-fail tests: !fail_count! correctly rejected ^(!fail_msg_ok! with verified message, !fail_no_err! without .err reference^)
if !fail_msg_bad! gtr 0 (
    echo Wrong error messages: !fail_msg_bad!
)
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
for /R "tests\fail" %%f in (*_actual.err) do del /Q "%%f" 2>nul

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
