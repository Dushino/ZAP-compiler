@echo off
setlocal enabledelayedexpansion

REM ------------------------------------------------------------
REM 1) Vytvoř seznam adresářů v dočasném souboru
REM ------------------------------------------------------------
dir /b /ad | sort > dirlist.tmp

set /a count=0

REM ------------------------------------------------------------
REM 2) Pro každý adresář vytvoř nové jméno a přejmenuj
REM ------------------------------------------------------------
for /f "usebackq delims=" %%d in ("dirlist.tmp") do (
    set "oldname=%%d"

    REM extrahuj část za pomlčkou
    for /f "tokens=1,* delims=-" %%a in ("%%d") do (
        set "suffix=%%b"
    )

    REM inkrementuj čítač
    set /a count+=1

    REM vytvoř nové číslo s nulami
    set "num=00!count!"
    set "num=!num:~-3!"

    set "newname=!num!-!suffix!"

    echo Renaming: "%%d"  →  "!newname!"
    ren "%%d" "!newname!"

    REM --------------------------------------------------------
    REM Přejmenuj soubory uvnitř adresáře
    REM --------------------------------------------------------
    pushd "!newname!" >nul

    for %%f in (*.*) do (
        set "ext=%%~xf"
        ren "%%f" "!newname!!ext!"
    )

    popd >nul
)

del dirlist.tmp
echo Hotovo.
