

.define DEBUG

.ifdef DEBUG
byte DEBUGVAR @40000 = 1
.else
byte NODEBUGVAR @40001 = 2
.endif

.undef DEBUG

.ifndef DEBUG
byte NODEBUGVAR @40003 = 4
.else
byte DEBUGVAR @40002 = 3
.endif


proc main()
    DEBUGVAR = $11
    NODEBUGVAR = $22
end

