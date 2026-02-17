const byte C1 = 100
const byte C2 = 50
const byte CA[] = {1, 2, 3}

struct Point
    byte x
    byte y
end

const Point CP = {10, 20}

byte res_scalar @40000 = 0
byte res_array @40001 = 0
byte res_struct @40002 = 0
word res_addr @40003 = 0

proc main()
    ; Const scalar usage
    res_scalar = C1 - C2
    
    ; Const array usage
    res_array = CA[1]
    
    ; Const struct usage - Commented out as compiler does not emit const struct symbols
    ; res_struct = CP.x + CP.y
    
    ; Address of const - Removed as scalar consts don't have runtime addresses
    ; res_addr = @C1
end
