; Check that pointer arrays are initialized correctly (2 bytes per element)

byte a = 10
byte b = 20
byte c = 30
byte d = 40

; Array of pointers to bytes
byte ^ptr_arr[4] = { $1000, $2000, $3000, $4000 }

proc main()
    a = 0
    ; Look for the loop comparing CPX #...
    ; Correct: CPX #8 (4 elements * 2 bytes)
    ; Bug:     CPX #4 (4 elements * 1 byte)
end
