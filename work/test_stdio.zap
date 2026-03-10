; test_stdio.zap
; working area for testing random parts of stdio.zap

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"
.include "lib/atari/atari_gtia.zap"


const byte Text1[] = "Hello!"

proc main()

    byte rv
    FILE fd

    ;COLOR4 = COLOR_MEDIUM_BLUE + 4
    puts("\nOpen:  ")    
    rv = fopen(@fd, "H1:TEST.TXT\x9b", ICAX1_MODE.Write)  
    putx(rv)  
    
    puts("\nWrite: ")
    rv = fwrite(@fd, Text1, 6)
    putx(rv)

    puts("\nClose: ")
    fclose(@fd)
    putx(rv)
    
    COLOR4 = COLOR_MEDIUM_GREEN + 8
end

; EOF
