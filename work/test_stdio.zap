; test_stdio.zap
; working area for testing random parts of stdio.zap

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"
.include "lib/string.zap"
.include "lib/atari/atari_gtia.zap"



const byte Text1[] = "Hello!"
const byte FName[] = "D1:TEST2.TXT\x9b"


proc main()

    byte rv
    FILE fd
        
    puts("Open:  ")    
    rv = fopen(@fd, FName, 8)  
    
    puts("Write: ")
    rv = fwrite(@fd, Text1, strlen(Text1))
    
    puts("Close: ")
    fclose(@fd)
    
    COLOR4 = COLOR_MEDIUM_GREEN + 8
end

; EOF
