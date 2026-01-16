; pointers declarations
; manually check generated code

byte ^ptr11
byte ^ptr12 @12
byte ^ptr13 @14 = %101

word ^ptr21
word ^ptr22 @16
word ^ptr23 @18 = 512   
word ^ptr24 = 'a''b'

word DLIST @560        

byte ^ptr25 = DLIST

; main -----------------------------------------
proc main()
end

