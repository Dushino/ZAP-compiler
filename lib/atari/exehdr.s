; Atari COM/EXE header
.import __RAM_START__, __RAM_LAST__

.segment "COMHEADER"
    .word $FFFF     		; block marker
    .word __RAM_START__		; load address
    .word __RAM_LAST__     	; end address
