; GAP-14: PORT struct field access patterns
; Tests all four combinations of #RD/#WR on struct fields,
; plus field-without-modifier inheriting struct-level #PORT default.
;
; PORT1 is at @40000 (0x9C40); layout:
;   byte rw_field    @ 0x9C40   (no modifier  → inherits both rd+wr)
;   byte rd_field    @ 0x9C41   (#RD          → read-only)
;   byte wr_field    @ 0x9C42   (#WR          → write-only)
;   byte rdwr_field  @ 0x9C43   (#RD #WR      → explicit both)
;
; result @40008 (0x9C48)

byte result @40008 = 0

struct MyPort #PORT
    byte rw_field           ; no modifier: inherits both rd+wr from struct-level #PORT
    byte rd_field   #RD     ; read-only field
    byte wr_field   #WR     ; write-only field
    byte rdwr_field #RD #WR ; explicit both read and write
end

MyPort PORT1 @40000 #PORT

proc main()
    ; read rd_field up front (declaration must precede statements)
    byte v = PORT1.rd_field  ; compiler permits read; value is 0 (memory starts zero)

    ; --- check 1: rw_field inherits both — write then read back ---
    PORT1.rw_field = 42
    if PORT1.rw_field == 42
        result = result + 1     ; 1: inherited rd+wr works for both directions
    end

    ; --- check 2: rdwr_field (explicit #RD #WR) — write then read back ---
    PORT1.rdwr_field = 77
    if PORT1.rdwr_field == 77
        result = result + 1     ; 2: explicit #RD #WR works for both directions
    end

    ; --- check 3: rd_field (#RD only) — compiler allows read ---
    ; Memory at rd_field offset starts at 0 (no write path exists on this field)
    if v == 0
        result = result + 1     ; 3: #RD field is readable (value is 0)
    end

    ; --- check 4: wr_field (#WR only) — compiler allows write ---
    PORT1.wr_field = 55
    result = result + 1         ; 4: #WR field is writable (reaching here = success)
end
