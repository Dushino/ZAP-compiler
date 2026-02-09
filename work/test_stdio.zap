; test_stdio.zap
; working area for testing random parts of stdio.zap

.define ATARI
.include "lib/stdio.zap"

proc main()

    byte ch

    cls()

    PLAYF2 = COLOR_GREEN3 + 4


    ch = getchar()
    while ch != 27
        putchar(ch)
        ch = getchar()
    end 

    PLAYF4 = COLOR_BLUE1  + 2
end
