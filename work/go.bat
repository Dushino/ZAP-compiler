del *.s
del *.o
del *.com

zapc.exe -I lib -6502 -D atari -o test_stdio.s test_stdio.zap
ca65 test_stdio.s -o test_stdio.o
ld65 -C ..\cfg\my_atari.cfg  test_stdio.o -o test_stdio.com
C:\Users\dusan.holub\local\Altirra\Altirra64.exe /w /basic /run test_stdio.com
