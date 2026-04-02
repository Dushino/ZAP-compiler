; stdio.zap
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


/*
    * puts	výstup do stdout (bez formátování)
    * gets	vstup ze stdin (bez formátování)
    * getchar	zadání jednoho znaku ze stdin
    * putchar	výstup jednoho znaku do stdout
  

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

.module "stdio"

.ifdef ATARI
    .include "./atari/atari_stdio.zap"
.endif

.ifdef SBC
    .include "./sbc/sbc_stdio.zap"   
.endif

