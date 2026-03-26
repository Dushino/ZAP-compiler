; test_stdio.zap
; working area for testing random parts of stdio.zap

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"
.include "lib/string.zap"
.include "lib/atari/atari_gtia.zap"


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
    ; byte name[33]       ; 3 (device D1: ) + 14 (filename) + 1 (separator for rename) + 14 (filename) + 1 (0) = 33 
    byte buf[32]
    
    puts(MsgTest1)
        
    puts("Open:   ")    
    rv += fopen(@fd, FName, ICAX1_Mode.Write)  
    putx(rv)                
    puts("\nWrite:  ")
    rv += fwrite(@fd, Text1, strlen(Text1))
    putx(rv)    
    puts("\nClose:  ")
    fclose(@fd)
    putx(rv)    
        
    puts("\n\nOpen:   ")    
    rv += fopen(@fd, FName, ICAX1_Mode.Read)  
    putx(rv)
    puts("\nRead:   ")    
    rv += fread(@fd, buf, 5)
    putx(rv)
    putchar('-')
    buf[5] = 0
    puts(buf)
    rv += fgetc(@fd)
    putchar(rv)
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

; output: 
; ZAP!     1899 prime numbers 


; benchmarks according to https://github.com/pedromagician/Atari800-benchmarks
; TEST E:
; Atari Basic:              16003 = 320.06s
; Turbo Basic:               6744 = 134.88s
; Atari Basic compiled I:     950 =  19.00s
; Atari Basic compiled F:    4660 =  93.20s
; Turbo Basic compiled:      1906 =  38.12s
; FastBasic	Byte-code	              5.50s
; Action!:               76 / 50  =   1.52s  with SDMCTL=0
; ZAP!           $1F0 = 496 / 500 =   0.992s with SDMCTL=0
proc sieve()
    const word max = 8192
    byte flags[max]
    word count = 0
    word i, prime, k
        
    for i=0 to max
        flags[i] = 1
    end

    for i=0 to max
        if flags[i]
            prime = i*2+3
            k = i + prime
    
            while k <= max-1
                flags[k] = 0
                k += prime
            end
            count += 1
        end
    end
    
end


proc main() 
    byte i
    byte time[3] @18    ; Atari timer
    byte SDMCTL @559
    
    ; puts(MsgTests)
    COLOR4 = GTIA_Colors.DARK_ORANGE + 4
    SDMCTL = 0

    ; zero timer
    time[0] = 0
    time[1] = 0
    time[2] = 0

    for i = 0 to 10
        sieve()
    end
    ; rv = test_files()

    ; 10 iterations give $0003B4 (948 dec) = 1.896 sec / iteration
    putx(time[0])    
    putx(time[1])
    putx(time[2])

    COLOR4 = GTIA_Colors.MEDIUM_GREEN + 4
    SDMCTL = 34

end

; EOF
