@echo off
del *.s
del *.o
del *.xex

rem python ..\compiler.py 
rem exit /b

python ..\compiler.py -O1 -I ../lib -6502 -D AUTOSTART -cfg ../cfg/my_atari.cfg -o test_stdio.s test_stdio.zap || exit /b
ca65 test_stdio.s -o test_stdio.o  || exit /b
ld65 -C ..\cfg\my_atari.cfg  -m test_stdio.map test_stdio.o -o test_stdio.xex  || exit /b
da65 -m -v -v -v -S 0x4000 --comments 3 test_stdio.xex -o test_stdio.d65
copy test_stdio.xex disk\AUTORUN.SYS
dir2atr -E -b DOS25 test_stdio.atr disk
C:\Users\dusan.holub\local\Altirra\Altirra64.exe /w /nobasic /bootrw test_stdio.atr
adir -1 -r -t test_stdio.atr
