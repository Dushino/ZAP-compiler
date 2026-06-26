; Test: #ZP variable that won't fit in the available ZP budget
; Using -ZPSTART 254 leaves only 2 bytes; the #ZP array needs 4.
byte arr[4] #ZP

proc main()
    arr[0] = 1
end
