.import __RAM_START__, __RAM_LAST__

.segment "AUTOSTRT"
    .word $FFFF     		; second block marker
    .word __RAM_START__		; RUN address
    .word __RAM_LAST__    	; last byte
