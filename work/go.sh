rm *.s
rm *.o
rm *.com

#cd ..
#./make_dist.sh
#cd work

zapc -6502 -I lib -o test_stdio.s test_stdio.zap
ca65 test_stdio.s -o test_stdio.o
ld65 -C ../cfg/my_atari.cfg  test_stdio.o -o test_stdio.com
atari800 test_stdio.com
