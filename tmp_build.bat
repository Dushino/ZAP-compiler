@echo off
python compiler.py tests\pass\136-pointer-math\136-pointer-math.zap -o test.s
if errorlevel 1 exit /b 1
ca65 -I lib -t none --cpu 65c02 -g test.s -o test.o
if errorlevel 1 exit /b 1
ca65 -I lib -t none --cpu 65c02 -g lib\atari\exehdr.s -o exehdr.o
if errorlevel 1 exit /b 1
ld65 -C cfg\my_atari.cfg test.o exehdr.o -o test.com
if errorlevel 1 exit /b 1
6502_simulator --cpu 65c02 --config tests\pass\136-pointer-math\136-pointer-math.json --verbose --dump-file tests\pass\136-pointer-math\136-pointer-math.ref test.com
if errorlevel 1 exit /b 1
echo SUCCESS
