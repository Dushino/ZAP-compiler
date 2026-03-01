; Instance-level #PORT #WR makes all unqualified fields write-only.
; Reading from an unqualified field (no field modifier) must be rejected.

struct SomePort #PORT
    byte DATA           ; no field modifier — inherits instance direction
    byte STATUS #WR     ; explicit #WR (consistent with instance, but explicit)
end

SomePort PORT1 @40000 #PORT #WR    ; instance is write-only overall

proc main()
    byte v
    v = PORT1.DATA    ; ERROR: read from field that falls back to instance #WR
end
