byte result @40000 = 0

proc main()
    long my_long = 65536
    long end_val = 65540
    byte for_count = 0
    long switch_val = 131072
    
    ; 1. IF Truthiness
    if my_long
        result = result + 1
    else
        result = 255
    end
    
    ; 2. WHILE Truthiness
    while my_long
        result = result + 1
        my_long = 0
    end
    
    ; 3. FOR loop (LONG bounds)
    my_long = 65536
    for my_long = my_long to end_val step 1
        for_count = for_count + 1
    end
    if for_count == 4
        result = result + 1
    end

    ; 4. SWITCH (LONG case)
    switch switch_val
        case 65536
            result = 255
            break
        case 131072
            result = result + 1
            break
        default
            result = 255
    end
end
