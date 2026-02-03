; test_stdio.zap
; working area for testing random parts of stdio.zap

.define ATARI
.include "/home/dusan/src/ZAP-compiler/work/lib/stdio.zap"

proc main()

    byte ch

    cls()
    PLAYF2 = COLOR_GREEN3 + 4
    ch = getchar()
    PLAYF4 = COLOR_BLUE1  + 2

end


