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

byte ^dlstart @560
word ^scrptr 
byte ^vram

byte cur_xpos, cur_ypos     ; cusros position on the screen
const byte MAX_XPOS = 39
const byte MAX_YPOS = 24    

proc cls()
    word i

    cur_xpos = 0
    cur_ypos = 0    

    scrptr = dlstart
    scrptr = scrptr + 4
    vram = scrptr^

    vram^ = 1

end
