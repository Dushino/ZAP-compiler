; Instance-level #PORT #RD makes all unqualified fields read-only.
; Writing to an unqualified field (no field modifier) must be rejected.

struct SomePort #PORT
    byte DATA           ; no field modifier — inherits instance direction
    byte STATUS #RD     ; explicit #RD (consistent with instance, but explicit)
end

SomePort PORT1 @40000 #PORT #RD    ; instance is read-only overall

proc main()
    PORT1.DATA = 42    ; ERROR: write to field that falls back to instance #RD
end
