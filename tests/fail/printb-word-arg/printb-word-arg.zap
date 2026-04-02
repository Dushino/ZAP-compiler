; printb should reject word argument (too wide)

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"

proc main()
    word w = 1000
    printb(w)           ; ERROR: word too wide for byte parameter
end
