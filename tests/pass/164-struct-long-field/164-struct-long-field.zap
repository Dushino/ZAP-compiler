; GAP-20: LONG struct field read/write codegen
;
; Checks:
;   1: direct ident.long_field write + read (Identifier base)
;   2: arr[i].long_field write + read (SubscriptExpr base)
;   3: ptr^.long_field write + read (is_deref)
;   4: nested struct LONG field via FieldAccess->Identifier
;   5: array-of-struct nested LONG via FieldAccess->SubscriptExpr
;   6: myfunc().long_field read (CallExpr base)
;
; result @40000 — each passed check adds 1, expected = 6 = $06

struct Flat
    byte tag
    long val
    byte pad
end

struct Inner
    long n
end

struct Outer
    byte x
    inner sub
end

byte result @40000 = 0

flat s1
flat farr[3]
flat pt
flat^ fptr
outer ou
outer ouarr[2]
long rv

func flat make_flat(byte t, long v)
    flat r
    r.tag = t
    r.val = v
    r.pad = 0
    return r
end

proc main()
    ; check 1: direct ident.long_field write + read
    s1.tag = 1
    s1.val = $12345678
    s1.pad = 9
    if s1.val == $12345678
        result = result + 1
    end

    ; check 2: arr[i].long_field write + read (SubscriptExpr)
    farr[1].tag = 2
    farr[1].val = $ABCD1234
    farr[1].pad = 0
    if farr[1].val == $ABCD1234
        result = result + 1
    end

    ; check 3: ptr^.long_field write + read (is_deref)
    fptr = @pt
    pt.val = 0
    fptr^.val = $11223344
    if fptr^.val == $11223344
        result = result + 1
    end

    ; check 4: nested struct LONG (FieldAccess->Identifier)
    ou.x = 0
    ou.sub.n = $0A0B0C0D
    if ou.sub.n == $0A0B0C0D
        result = result + 1
    end

    ; check 5: array-of-struct nested LONG (FieldAccess->SubscriptExpr)
    ouarr[0].x = 0
    ouarr[0].sub.n = $DEADBEEF
    if ouarr[0].sub.n == $DEADBEEF
        result = result + 1
    end

    ; check 6: myfunc().long_field read (CallExpr base)
    rv = make_flat(7, $77665544).val
    if rv == $77665544
        result = result + 1
    end
end
