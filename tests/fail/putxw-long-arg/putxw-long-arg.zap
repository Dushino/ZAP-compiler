; putxw should reject long argument (too wide)

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"

proc main()
    long l = $12345678
    putxw(l)            ; ERROR: long too wide for word parameter
end
