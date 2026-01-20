; Test: BYTE Type Declaration and Usage
; 
; Purpose: Validates BYTE type variables work correctly
; Test stores values at address 40000 for memory validation

byte result @40000 = 0

proc main()
    byte x = 42
    byte y = 100
    byte z = x + y     ; 42 + 100 = 142, wraps to 142 % 256 = 142
    
    result = z
end
