; Test 146: arrays of structs — GAP-03 completeness
; Covers: constant-index field access, variable-index field access,
;         list-init with nested braces, for-loop access,
;         multi-dim (arr[i].array_field[j])
;
; struct Point: byte x, byte y  (2 bytes per element)
; struct Row:   byte col[3]     (3 bytes per element)
;
; Checks (result +1 each):
;  1.  pts[0].x = 11; pts[0].x == 11   (const-idx write, first field)
;  2.  pts[0].y = 22; pts[0].y == 22   (const-idx write, second field)
;  3.  pts[2].x = 33; pts[2].x == 33   (const-idx, third element)
;  4.  pts[2].y = 44; pts[2].y == 44   (const-idx, third element, second field)
;  5.  i=1; pts[i].x = 55; pts[1].x == 55   (var-idx write, first field)
;  6.  pts[i].y = 66; pts[1].y == 66         (var-idx write, second field)
;  7.  src[0].x == 1  (list-init, first element first field)
;  8.  src[0].y == 2  (list-init, first element second field)
;  9.  src[2].x == 5  (list-init, last element first field)
; 10.  loop: sum src[j].x for j=0..2 = 1+3+5=9; sum==9
; 11.  grid[1].col[2] = 77; grid[1].col[2] == 77  (multi-dim, const idx)
; 12.  j=0; grid[j].col[1] = 88; grid[0].col[1] == 88  (multi-dim, var idx)
;
; Expected result: 12 = $0C

byte result @40000 = 0

struct Point
    byte x
    byte y
end

struct Row
    byte col[3]
end

proc main()
    Point pts[4]
    Point src[3] = {{1, 2}, {3, 4}, {5, 6}}
    Row grid[2]
    byte i
    byte j
    byte sum

    ; --- 1-2: constant-index write + read ---
    pts[0].x = 11
    pts[0].y = 22
    if pts[0].x == 11
        result = result + 1     ; 1
    end
    if pts[0].y == 22
        result = result + 1     ; 2
    end

    ; --- 3-4: third element, both fields ---
    pts[2].x = 33
    pts[2].y = 44
    if pts[2].x == 33
        result = result + 1     ; 3
    end
    if pts[2].y == 44
        result = result + 1     ; 4
    end

    ; --- 5-6: variable-index write + read ---
    i = 1
    pts[i].x = 55
    pts[i].y = 66
    if pts[i].x == 55
        result = result + 1     ; 5
    end
    if pts[i].y == 66
        result = result + 1     ; 6
    end

    ; --- 7-9: list-init access ---
    if src[0].x == 1
        result = result + 1     ; 7
    end
    if src[0].y == 2
        result = result + 1     ; 8
    end
    if src[2].x == 5
        result = result + 1     ; 9
    end

    ; --- 10: for-loop over struct array ---
    sum = 0
    for j = 0 to 3
        sum = sum + src[j].x
    end
    if sum == 9
        result = result + 1     ; 10
    end

    ; --- 11-12: multi-dim — arr[i].array_field[j] ---
    grid[1].col[2] = 77
    if grid[1].col[2] == 77
        result = result + 1     ; 11
    end
    j = 0
    grid[j].col[1] = 88
    if grid[j].col[1] == 88
        result = result + 1     ; 12
    end
end
