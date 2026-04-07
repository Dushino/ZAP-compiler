; test_stdio.zap
; working area for testing random parts of stdio.zap
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


.ifndef ATARI
    .define ATARI
.endif

.include "../lib/stdio.zap"
.include "../lib/types.zap"
.include "../lib/string.zap"
.include "../lib/atari/atari_gtia.zap"


const byte MsgTests[] = "stdio.zap tests ------------------\n\n"
const byte MsgTest1[] = "Files:\n"
const byte Text1[] = "Hello!"
const byte FName[] = "D1:TEST.TXT"


proc prnrv(byte rv)
    putx(rv)
    puts("\n")
end


func byte test_files()
    byte rv = 0
    
    FILE fd
    byte oldname[] = "D1:TEST.TXT"
    byte newname[] = "NEWN.ABC"
    byte buf[32]
    byte ch, i
    
    puts(MsgTest1)
        
    puts("Open:   ")    
    rv += fopen(@fd, FName, ICAX1_Mode.Write)  
    putx(rv)                
    puts("\nWrite:  ")
    rv += fwrite(@fd, Text1, strlen(Text1))
    putx(rv)    
    puts("\nPut:    ")
    rv += fputc(@fd, 'X')
    putx(rv)    

    puts("\nClose:  ")
    fclose(@fd)
    putx(rv)    
        
    puts("\n\nOpen:   ")    
    rv += fopen(@fd, FName, ICAX1_Mode.Read)  
    putx(rv)
    /*
    puts("\nRead:   ")    
    rv += fread(@fd, buf, 7)
    putx(rv)
    putchar('-')
    buf[7] = 0
    puts(buf)
    */

    puts("\nGet:    ")
    for i=0 to 10
        ch = fgetc(@fd)
        putx(ch)
        putx(fd.fd)
        putx(ferror(@fd))
        putchar(' ')        
    end

    puts("\nClose:  ")
    fclose(@fd)
    putx(rv)

    puts("\n\nVysledek:")
    prnrv(rv)

    ;puts("Rename: ")
    ;rv = rename(FName, newname)
    ;puts("Remove: ")
    ;rv = remove(FName)    

    return rv
end


proc main() 
    byte rv
    
    ; puts(MsgTests)
    rv = test_files()

end

; EOF
