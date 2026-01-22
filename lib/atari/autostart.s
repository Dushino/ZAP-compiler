.import __START, __END

.segment "AUTOSTART"
    .word $FFFF     ; second block marker
    .word __START   ; RUN address
    .word __END     ; last byte
