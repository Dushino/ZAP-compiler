; test_stdio.zap
; working area for testing random parts of stdio.zap

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"
.include "lib/atari/atari_gtia.zap"

proc main()

    byte rv
    FILE fd

    COLOR4 = COLOR_MEDIUM_BLUE + 4
    
    rv = fopen(fd, "D:TEST.TXT", ICAX1_COMMANDS.APPEND)
    putx(rv)
    
    COLOR4 = COLOR_MEDIUM_GREEN + 8
end

; EOF
