#!/bin/bash
rm -f *.s
rm -f *.o
rm -f *.com

python3 ../compiler.py -O1 -I lib -6502 -D ATARI -D AUTOSTART -o test_stdio.s test_stdio.zap || exit
ca65 test_stdio.s -o test_stdio.o || exit
ld65 -C ../cfg/my_atari.cfg -m test_stdio.map test_stdio.o -o test_stdio.xex || exit
da65 -m -v -v -v -S 0x4000 --comments 3 test_stdio.xex -o test_stdio.d65
cp test_stdio.xex disk_in/AUTORUN.SYS
atari800 test_stdio.xex


