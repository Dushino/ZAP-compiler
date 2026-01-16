; pointers declarations
; manually check generated code

byte ^ptr11             ; $82, $83
byte ^ptr12 @$a0        ; $a0, $a1
byte ^ptr13 @$86 = %101 ; $84, $85

word ^ptr21             ; $88, $89 
word ^ptr22 @$a2        ; $a2, $a3
word ^ptr23 @$8c = 513  ; $8a, $8b

word ^ptr24 = 'a''b'    ; $8c, $8d

word DLIST @560        

byte ^ptr25 = DLIST     ; $8e, $8f

; main -----------------------------------------
proc main()
end

