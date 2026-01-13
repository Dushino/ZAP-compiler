; This file defines the EXE header and main chunk load header for Atari executables

.import __START, __END

; -----------------------------------------------
; Executable file header
.segment                "COMHEADER"
                        .word $ffff
                        .word __START
                        .word __END

