; test_stdio.zap
; working area for testing random parts of stdio.zap

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"
.include "lib/atari/atari_gtia.zap"

proc main()

    byte ch
    byte ^ptr

    COLOR4 = COLOR_MEDIUM_BLUE + 4
    
    
    find_free_IOCB()
    
    COLOR4 = COLOR_MEDIUM_GREEN + 8
end

; EOF
