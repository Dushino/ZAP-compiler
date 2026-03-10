rm -f *.s
rm -f *.o
rm -f *.com

#cd ..
#./make_dist.sh
#cd work

python3 ../compiler.py -O1 -I lib -6502 -D ATARI -o test_stdio.s test_stdio.zap || exit
# python3 ../compiler.py -O1 -I lib -o test_stdio_65c02.s test_stdio.zap || exit
# zapc -6502 -I lib -o test_stdio.s test_stdio.zap || exit
ca65 test_stdio.s -o test_stdio.o || exit
ld65 -C ../cfg/my_atari.cfg  test_stdio.o -o test_stdio.xex || exit
#cp test_stdio.xex ./disk/RUNTIME.AR0
cp test_stdio.xex ./disk/AUTORUN.SYS
atari800 -H1 disk -basic ./disk/AUTORUN.SYS


