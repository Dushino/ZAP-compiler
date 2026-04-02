; printw should reject long argument (too wide)

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"

proc main()
    long l = 100000
    printw(l)           ; ERROR: long too wide for word parameter
end
