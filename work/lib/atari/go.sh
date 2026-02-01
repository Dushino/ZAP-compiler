rm *.s
rm *.o
rm *.com

zapc -6502 -D -Ilib -o atari_stdio.s atari_stdio.zap
ca65 atari_stdio.s -o atari_stdio.o
ld65 -C ../../../cfg/my_atari.cfg  atari_stdio.o -o atari_stdio.com
atari800 atari_stdio.com
