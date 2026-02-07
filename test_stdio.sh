#!/bin/bash
rm work/*.s
rm work/*.o
rm work/*.com

/home/dusan/src/ZAP-compiler/.venv/bin/python compiler.py work/test_stdio.zap -6502 -I work/lib -o work/test_stdio.s || exit
ca65 work/test_stdio.s -o work/test_stdio.o || exit
ld65 -C cfg/my_atari.cfg  work/test_stdio.o -o work/test_stdio.com || exit
atari800 work/test_stdio.com
