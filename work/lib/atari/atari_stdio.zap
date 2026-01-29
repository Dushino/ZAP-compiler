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

byte cur_xpos, cur_ypos     ; cusros position on the screen
const byte MAX_XPOS = 39
const byte MAX_YPOS = 24    


/*
    exehdr and autostart data area
    needed by linker for proper atari .com file generation
*/
proc atari_file_data_area()
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



proc cls()
    word i
    byte color_bk @712
    byte ^dlstart @560      ; system storage for DL address
    word ^dlptr             ; pointer into display list
    byte ^vram
        
    dlptr = dlstart         ; copy display list address into ZP pointer        
    dlptr = dlptr + 2       ; skip first four bytes (2xWORD) of display list
    vram = dlptr^           ; get screen memory address from display list
    
    vram^ = 1
    ;vram = vram + 1
    ;vram^ = 2

    ;vram = adr           ; get screen memory address from display list
    ;vram^ = 1
    ;vram  = vram + 1
    ;vram^ = 2
    ;dlptr^ = 1
    ; vram = dlptr

    ; vram^ = 1

    color_bk = 12*16+2
    cur_xpos = 0
    cur_ypos = 0    

end
