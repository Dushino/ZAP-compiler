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
        
    puts("Open:  ")    
    rv = fopen(@fd, "H1:TEST.TXT\x9b", ICAX1_MODE.Write)  
    
    puts("Write: ")
    rv = fwrite(@fd, Text1, 6)
    
    puts("Close: ")
    fclose(@fd)
    
    COLOR4 = COLOR_MEDIUM_GREEN + 8
end

; EOF
