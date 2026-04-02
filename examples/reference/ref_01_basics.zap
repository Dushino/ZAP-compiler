; Example: ref_01_basics.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, sections "Getting Started" + "Basic Concepts" (lines 29-88)
;
; Demonstrates: minimal program, case sensitivity, comments
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


byte myVar = 0

proc main()
    ; This is a comment
    byte x = 5  ; Initialize x to 5
    myVar = x
end
