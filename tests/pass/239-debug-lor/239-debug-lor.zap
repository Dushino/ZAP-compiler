; Debug test to identify which LOR check fails in 227
; Stores intermediate results at known addresses
byte r1 @$0200 = 0  ; check 1 result
byte r2 @$0201 = 0  ; check 2 result  
byte r3 @$0202 = 0  ; check 3 result
byte r4 @$0203 = 0  ; check 4 result
byte r5 @$0204 = 0  ; check 5 result

byte arr[3] = {0, 5, 0}
word warr[2] = {0, $0100}

struct Rec
    byte flag
end
Rec r

proc main()
    r.flag = 1

    if arr[0] || arr[1]
        r1 = 1
    end

    if arr[0] || arr[2]
    else
        r2 = 1
    end

    if warr[0] || warr[1]
        r3 = 1
    end

    if r.flag || 0
        r4 = 1
    end

    if arr[1] && arr[1]
        r5 = 1
    end
end
