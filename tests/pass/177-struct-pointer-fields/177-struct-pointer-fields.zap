; Test: Pointer fields in structs + word struct field init fix
; Checks: byte^, word^, struct^ field declarations; write and read through pointer fields.
; Also verifies that a struct with a word field is correctly initialised (both bytes stored).

struct Target
    byte  val1
    word  wval
    byte  val2
end

struct Holder
    byte^   bptr
    word^   wptr
    Target^ sptr
end

byte   bdata  @$9C40 = 10
word   wdata  @$9C41 = 1000
Target tdata  @$9C43 = { 55, 300, 10 }
Holder h      @$9C48

byte   read_b    @$9C50
word   read_w    @$9C51
byte   read_s    @$9C53
word   read_wval @$9C54

proc main()
    ; Assign addresses to pointer fields
    h.bptr = @bdata
    h.wptr = @wdata
    h.sptr = @tdata

    ; Write through pointer fields
    h.bptr^ = 20
    h.wptr^ = 2000
    h.sptr^.val1 = 77

    ; Read through pointer fields
    read_b    = h.bptr^
    read_w    = h.wptr^
    read_s    = h.sptr^.val1
    read_wval = h.sptr^.wval
end
