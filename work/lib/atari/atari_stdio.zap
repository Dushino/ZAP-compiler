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


byte cur_xpos, cur_ypos     ; cursor position on the screen
const byte MAX_XPOS = 39
const byte MAX_YPOS = 24    

byte ^vlstart[MAX_YPOS]

; initialize internals for faster screen IO
proc CONSTRUCTOR() 
    word dlstart @560      ; system storage for DL address
    word ^vram
    byte ^data
    byte i
    
    vram = dlstart + 4
    data = vram^
    ; data^ = 1
    vlstart[0] = data
    for i = 1 to MAX_YPOS - 1        
        vlstart[i] = data
        data = data + MAX_XPOS + 1
    end
    vlstart[0]^ = 1
    vlstart[1]^ = 2
end


/*
    COMHEADER and AUTOSTRT data area
    needed by linker for proper atari .com file generation
*/
proc atari_file_data_area() #KEEP #NOEXPORT
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
    Clear Screen and reset cursor position
*/
proc cls()
    cur_xpos = 0
    cur_ypos = 0    
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


