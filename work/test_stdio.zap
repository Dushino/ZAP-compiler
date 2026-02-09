; test_stdio.zap
; working area for testing random parts of stdio.zap

.define ATARI
.include "lib/stdio.zap"

proc main()

    byte ch

    ; cls()

    PLAYF2 = COLOR_GREEN3 + 4

    ch = getchar()
    PLAYF4 = COLOR_BLUE1  + 2
end
