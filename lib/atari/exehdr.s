; Atari COM/EXE header
.import __START, __END

.segment "EXEHDR"
    .word $FFFF     ; block marker
    .word __START   ; load address
    .word __END     ; end address
