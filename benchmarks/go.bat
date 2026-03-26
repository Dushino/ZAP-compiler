@echo off
del *.s
del *.o
del *.xex

python ..\compiler.py -O1 -I lib -6502 -D AUTOSTART -cfg ../cfg/my_atari.cfg -o benchmarks.s benchmarks.zap || exit /b
ca65 benchmarks.s -o benchmarks.o  || exit /b
ld65 -C ..\cfg\my_atari.cfg  -m benchmarks.map benchmarks.o -o benchmarks.xex  || exit /b
da65 -m -v -v -v -S 0x4000 --comments 3 benchmarks.xex -o benchmarks.d65
copy benchmarks.xex disk\AUTORUN.SYS
dir2atr -E -b DOS25 benchmarks.atr disk
C:\Users\dusan.holub\local\Altirra\Altirra64.exe /w /nobasic /bootrw benchmarks.atr
adir -1 -r -t benchmarks.atr
