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

.module atari_stdio

; ATARI colors
const COLOR_BLACK   = $00
const COLOR_YELLOW1 = $10
const COLOR_ORANGE2 = $20
const COLOR_RED1    = $30
const COLOR_VIOLET1 = $40
const COLOR_VIOLET2 = $50
const COLOR_VIOLET3 = $60
const COLOR_BLUE1   = $70
const COLOR_BLUE2   = $80
const COLOR_BLUE3   = $90
const COLOR_GREEN1  = $A0
const COLOR_GREEN2  = $B0
const COLOR_GREEN3  = $C0
const COLOR_GREEN4  = $D0
const COLOR_YELLOW2 = $E0
const COLOR_BROWN   = $F0


byte cur_xpos, cur_ypos     ; cusros position on the screen
const byte MAX_XPOS = 39
const byte MAX_YPOS = 24    

; initialize internals for faster screen IO
proc CONSTRUCTOR()  ; Fixme: #KEEP #NOEXPORT
    byte ^dlstart @560      ; system storage for DL address
    word ^dlptr             ; pointer into display list
    byte ^vram
        
    dlptr = dlstart         ; copy display list address into ZP pointer        
    dlptr = dlptr + 2       ; skip first four bytes (2xWORD) of display list
    vram = dlptr^           ; get screen memory address from display list
    
    vram^ = 1
end


/*
    COMHEADER and AUTOSTRT data area
    needed by linker for proper atari .com file generation
*/
; Fixme: .segment directives should be inside ASM block
proc atari_file_data_area() ; Fixme: #KEEP #NOEXPORT
    .segment "COMHEADER"
    asm
        .import __RAM_START__, __RAM_LAST__
        .word $FFFF     		; second block marker
        .word __RAM_START__		; RUN address
        .word __RAM_LAST__    	; last byte
    end
    .segment "AUTOSTRT"
    asm
        .import __RAM_START__, __RAM_LAST__
        .word $FFFF     		; second block marker
        .word __RAM_START__		; RUN address
        .word __RAM_LAST__    	; last byte
    end
    .segment "CODE"
end


/*
    Clear Screen and reset cursor position
*/
proc cls()
    word i
    byte color_bk @712

    color_bk = COLOR_GREEN2 + 2
    cur_xpos = 0
    cur_ypos = 0    

end
