; Test 147: arrays inside struct fields — GAP-04 completeness
; Covers: declaration, list-init, constant-index access, variable-index access,
;         for-loop access, struct copy (copies array fields), word array field
;
; struct BArr: byte data[4]  (4 bytes)
; struct WArr: word vals[3]  (6 bytes)
;
; Checks (result +1 each):
;  1.  s.data[0] = 11; s.data[0] == 11    (const-idx byte write + read)
;  2.  s.data[3] = 44; s.data[3] == 44    (last element, const-idx)
;  3.  i=2; s.data[i] = 33; s.data[2] == 33  (var-idx write, const-idx verify)
;  4.  s.data[i] == 33                        (var-idx read, i=2)
;  5.  p = {{1,2,3,4}}; p.data[0] == 1   (list-init, nested braces for array field)
;  6.  p.data[3] == 4                     (list-init last element)
;  7.  loop: sum p.data[j] for j=0..3 = 1+2+3+4=10; sum==10
;  8.  dst = p (struct copy); dst.data[0] == 1
;  9.  dst.data[3] == 4
; 10.  w.vals[0] = 1000; w.vals[0] == 1000   (word array field, const-idx)
; 11.  k=1; w.vals[k] = 2000; w.vals[1] == 2000  (word array field, var-idx write)
; 12.  w.vals[k] == 2000                          (word array field, var-idx read)
;
; Expected result: 12 = $0C

byte result @40000 = 0

struct BArr
    byte data[4]
end

struct WArr
    word vals[3]
end

proc main()
    BArr s
    BArr p = {{1, 2, 3, 4}}
    BArr dst
    WArr w
    byte i
    byte j
    byte k
    byte sum

    ; --- 1-2: constant-index byte write + read ---
    s.data[0] = 11
    s.data[3] = 44
    if s.data[0] == 11
        result = result + 1     ; 1
    end
    if s.data[3] == 44
        result = result + 1     ; 2
    end

    ; --- 3-4: variable-index byte write + read ---
    i = 2
    s.data[i] = 33
    if s.data[2] == 33
        result = result + 1     ; 3
    end
    if s.data[i] == 33
        result = result + 1     ; 4
    end

    ; --- 5-6: list-init ---
    if p.data[0] == 1
        result = result + 1     ; 5
    end
    if p.data[3] == 4
        result = result + 1     ; 6
    end

    ; --- 7: for-loop over array field ---
    sum = 0
    for j = 0 to 4
        sum = sum + p.data[j]
    end
    if sum == 10
        result = result + 1     ; 7
    end

    ; --- 8-9: struct copy copies array field ---
    dst = p
    if dst.data[0] == 1
        result = result + 1     ; 8
    end
    if dst.data[3] == 4
        result = result + 1     ; 9
    end

    ; --- 10-12: word array field ---
    w.vals[0] = 1000
    if w.vals[0] == 1000
        result = result + 1     ; 10
    end
    k = 1
    w.vals[k] = 2000
    if w.vals[1] == 2000
        result = result + 1     ; 11
    end
    if w.vals[k] == 2000
        result = result + 1     ; 12
    end
end
