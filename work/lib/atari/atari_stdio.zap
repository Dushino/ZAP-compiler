; atari_stdio.zap

/*
    * puts	    výstup do stdout (bez formátování)
    * gets	    vstup ze stdin (bez formátování)
    * getchar	zadání jednoho znaku ze stdin
    * putchar	výstup jednoho znaku do stdout
    * cls       vyčištění obrazovky
  

    * fopen	otevření souboru
    * fclose	zavření souboru
    * ferror	při chybě program vrací, že návratová hodnota se nerovná 0
    * feof	    kontrola, zda byl dosažen EOF (End-Of-File) souboru
    * rename	přejmenování souboru
    * remove	mazání souboru
    * fseek	    pohybování kurzorem v souboru
    * ftell	    zjištění aktuální pozice kurzoru v souboru
    * fread	    čtení dat ze souboru
    * fwrite	zápis dat do souboru
    * fgetc     čtení jednoho znaku ze souboru
    * fputc     zápis jednoho znaku do souboru
*/

.module "atari_stdio"


; ATARI colors
const byte COLOR_BLACK   = $00
const byte COLOR_YELLOW1 = $10
const byte COLOR_ORANGE2 = $20
const byte COLOR_RED1    = $30
const byte COLOR_VIOLET1 = $40
const byte COLOR_VIOLET2 = $50
const byte COLOR_VIOLET3 = $60
const byte COLOR_BLUE1   = $70
const byte COLOR_BLUE2   = $80
const byte COLOR_BLUE3   = $90
const byte COLOR_GREEN1  = $A0
const byte COLOR_GREEN2  = $B0
const byte COLOR_GREEN3  = $C0
const byte COLOR_GREEN4  = $D0
const byte COLOR_YELLOW2 = $E0
const byte COLOR_BROWN   = $F0


byte PCOLOR0 @704 
byte PCOLOR1 @705       
byte PCOLOR2 @706       
byte PCOLOR3 @707       
byte PLAYF0  @708       
byte PLAYF1  @709
byte PLAYF2  @710
byte PLAYF3  @711
byte PLAYF4  @712


byte cur_xpos, cur_ypos                     ; cursor position on the screen
const byte SCREEN_X_SIZE = 40
const byte SCREEN_Y_SIZE = 24

byte ^vlstart[SCREEN_Y_SIZE]    #noexport   ; vertical line start positions for each row of the screen
byte ^curptr                    #noexport   ; current position in the screen memory for output



; initialize internals for faster screen IO
proc CONSTRUCTOR() 
    word scrstart @88
    byte ^data
    byte i

    data = scrstart
    for i = 0 to SCREEN_Y_SIZE
        vlstart[i] = data
        data = data + SCREEN_X_SIZE   
    end
end



/*
    COMHEADER and AUTOSTRT data area
    needed by linker for proper atari .com file generation
*/
proc atari_file_data_area() #keep #noexport
    asm
        .segment "COMHEADER"
        .import __RAM_START__, __RAM_LAST__
        .word $FFFF     		; second block marker
        .word __RAM_START__		; RUN address
        .word __RAM_LAST__    	; last byte  

        .segment "AUTOSTRT"
        .import __RAM_START__, __RAM_LAST__
        .word $FFFF     		; second block marker
        .word __RAM_START__		; RUN address
        .word __RAM_LAST__    	; last byte

        .segment "CODE"        
    end
end


/*
    Fill memory with byte value
*/
proc memset(word dest, byte value, word count)
    word i
    byte ^ptr = dest

    for i = 0 to count
        ptr^ = value
        ptr = ptr + 1
    end
end


/*
    Copy memory from source to destination    
*/
proc memcpy(word dest, word src, word count)
    word i
    byte ^ptr1 = dest
    byte ^ptr2 = src

    for i = 0 to count
        ptr1^ = ptr2^
        ptr1 = ptr1 + 1
        ptr2 = ptr2 + 1
    end
end


/*
    Clear Screen and reset cursor position
*/
proc cls()
    word i
    byte ^ptr1 = vlstart[0]

    cur_xpos = 0
    cur_ypos = 0    
    curptr = vlstart[0]
    
    memset(vlstart[0], 0, SCREEN_X_SIZE * SCREEN_Y_SIZE)   ; clear color memory    
end


/*
    Wait for keyboard key press and return ATASCII code
*/
func byte getchar()
    byte ch

    asm
        LDA $e425
        PHA
        LDA $e424
        PHA
        rts        
        sta _GETCHAR_CH
    end

    return ch
end

/*
    putx - print HEX BYTE value as two characters
*/
proc putx(byte value)
    const byte hex_digits[] = "0123456789ABCDEF"
    putchar(hex_digits[value >> 4])
    putchar(hex_digits[value & $0F])
end



/*
    crlf - move cursor to the beginning of the next line, scroll screen if needed
*/
proc crlf()
    cur_xpos = 0

    if cur_ypos < SCREEN_Y_SIZE - 1
        cur_ypos = cur_ypos + 1
    else
        ; scroll screen up
        memcpy(vlstart[0], vlstart[1], (SCREEN_Y_SIZE - 1) * SCREEN_X_SIZE)
        memset(vlstart[SCREEN_Y_SIZE - 1], 0, SCREEN_X_SIZE)
    end
    curptr = vlstart[cur_ypos]
end


/*
    putchar to current screen location and move cursor forward, scroll screen if needed
*/
proc putchar(byte ch)

    switch ch
        case 10     ; newline
            crlf()
            return

        case '\t'    ; tab
            repeat
                putchar(' ')
            until (cur_xpos & $03) == 0
            return
    end

    ; convert ATASCII to screen code, handle inverse bit
    asm
                    lda _PUTCHAR_CH
                    asl a               ; shift out the inverse bit
                    adc #$c0            ; grab the inverse bit; convert ATASCII to screen code
                    bpl putchar_codeok        ; screen code ok?
                    eor #$40            ; needs correction
putchar_codeok:     lsr a               ; undo the shift
                    bcc putchar_sputc
                    eor #$80            ; restore the inverse bit            
putchar_sputc:
                    sta _PUTCHAR_CH
    end


    curptr^ = ch
    curptr = curptr + 1
    
    cur_xpos = cur_xpos + 1
    if cur_xpos >= SCREEN_X_SIZE
        cur_xpos = 0

        if cur_ypos < SCREEN_Y_SIZE - 1
            cur_ypos = cur_ypos + 1
            curptr = vlstart[cur_ypos]
        else
            crlf()
        end
    end
end


/*
    puts - print null-terminated string to the screen
*/
proc puts(byte ^str)
    byte ch
    ch = str^
    while ch != 0
        putchar(ch)
        str = str + 1
        ch = str^
    end
end

/*
    gets - read characters from keyboard until newline, store them in buffer as null-terminated string
*/
func byte gets(byte ^buffer, byte max_len)
    byte ch
    byte count = 0

    ch = getchar()
    while ch != 155 && count < max_len - 1
        putchar(ch)   ; echo the character back to the screen
        buffer^ = ch
        buffer = buffer + 1
        count = count + 1
        ch = getchar()
    end
    buffer^ = 0   ; null-terminate the string

    return count
end
