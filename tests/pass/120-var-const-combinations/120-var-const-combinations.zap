byte res_mixed @40000 = 0
byte res_array @40001 = 0
byte res_func @40002 = 0

const byte K = 10
const byte ARR_SIZE = 5

proc main()
    byte val = 5
    byte arr[ARR_SIZE]
    
    ; Mix const and var
    res_mixed = val + K
    
    ; Const array size
    arr[0] = 1
    arr[4] = 2
    res_array = arr[0] + arr[4]

    ; Const argument
    res_func = add_const(K, 2)
end

func byte add_const(byte a, byte b)
    return a + b
end
