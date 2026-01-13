; -*- c65asm -*-
; macros for Action! transpiler

.ifndef _MACROS_INC_
        _MACROS_INC_ .set 1


;TUI_MSGTIMER      .set $80

;TUI_WS_POPUP      .set TUI_WS_FRAME | TUI_WS_CAPTION
;TUI_WS_DIALOG     .set TUI_WS_POPUP | TUI_WS_MODAL


.importzp               TMPL, TMPH

; set immediate value to VAR8
.macro                  SETV8IMM name, value
                        lda #<value
                        sta name
.endmacro

; set immediate value to VAR16
.macro                  SETV16IMM name, value
                        lda #<value
                        sta name
                        lda #>value
                        sta name+1
.endmacro

; copy 8 bit value into variable
.macro                  LOAD8 name, value
                        lda value
                        sta name
.endmacro

; copy 16 bit value into variable
.macro                  LOAD16 name, value
                        lda value
                        sta name
                        lda value+1
                        sta name+1
.endmacro

; copy 8 bit value into (variable)
.macro                  LOAD8PTR name, value
                        lda value
                        sta (name)
.endmacro

; copy 16 bit value into (variable)
.macro                  LOAD16PTR name, value
                        lda value
                        sta (name)
                        ldy #1
                        lda value+1
                        sta (name),y
.endmacro

; add 8 bit immediate value into 8 bit variable
.macro                  ADD8IMM8 name, value
                        lda name 
                        clc
                        adc #<value
.endmacro

; add 16 bit immediate value into 16 bit variable
.macro                  ADD8IMM16 name, value
                        lda name
                        clc
                        adc #<value
                        sta name
                        lda name+1
                        adc #<(value+1)
                        sta name+1
.endmacro



.endif                                          ; _MACROS_INC_


