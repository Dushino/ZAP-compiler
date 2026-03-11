@echo off
del *.s
del *.o
del *.com

rem python ..\compiler.py 
rem exit /b

python ..\compiler.py -O1 -I lib -6502 -SEGC CODE -o test_stdio.s test_stdio.zap || exit /b
ca65 test_stdio.s -o test_stdio.o  || exit /b
ld65 -C ..\cfg\my_atari.cfg  test_stdio.o -o test_stdio.xex  || exit /b
copy test_stdio.xex ./disk/AUTORUN.SYS
C:\Users\dusan.holub\local\Altirra\Altirra64.exe /w /nobasic /run ./disk/AUTORUN.SYS 
