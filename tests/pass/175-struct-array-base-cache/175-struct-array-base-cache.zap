; Test 175: Phase 3 cache — consecutive struct array accesses with same variable index
; Verifies TMP0 is computed once and reused for array[i].field1 + array[i].field2
; Also verifies cache is correctly invalidated when index variable changes (for loop)
;
; struct Item: byte val, byte flag  (2 bytes each)
;
; Checks (result +1 each):
;  1.  items[0].val=1; items[0].flag=2;  items[0].val==1         (write+read cache)
;  2.  items[0].flag==2                                           (read cache hit)
;  3.  items[3].val=9; items[3].flag=8;  items[3].val==9         (different const idx)
;  4.  items[3].flag==8                                           (cache hit)
;  5.  i=2; items[i].val=5; items[i].flag=6; items[i].val==5     (variable idx)
;  6.  items[i].flag==6                                           (cache hit on var idx)
;  7.  for loop: sum items[j].val for j=0..3 = 1+?+5+9; check sum==15 (cache inval each iter)
;  8.  items[2].val==5 after loop (cache invalidated by loop, not corrupted)
;
; Expected result: 8 = $08

byte result @40000 = 0

struct Item
    byte val
    byte flag
end

proc main()
    Item items[4]
    byte i
    byte j
    byte sum

    ; --- 1-2: constant index 0, cache hit ---
    items[0].val = 1
    items[0].flag = 2
    if items[0].val == 1
        result = result + 1     ; 1
    end
    if items[0].flag == 2
        result = result + 1     ; 2
    end

    ; --- 3-4: constant index 3, cache hit ---
    items[3].val = 9
    items[3].flag = 8
    if items[3].val == 9
        result = result + 1     ; 3
    end
    if items[3].flag == 8
        result = result + 1     ; 4
    end

    ; --- 5-6: variable index, Phase 3 cache ---
    i = 2
    items[i].val = 5
    items[i].flag = 6
    if items[i].val == 5
        result = result + 1     ; 5
    end
    if items[i].flag == 6
        result = result + 1     ; 6
    end

    ; --- 7: for loop with cache invalidation each iteration ---
    sum = 0
    for j = 0 to 4
        sum = sum + items[j].val
    end
    if sum == 15
        result = result + 1     ; 7
    end

    ; --- 8: items[2].val not corrupted by loop ---
    if items[2].val == 5
        result = result + 1     ; 8
    end
end
