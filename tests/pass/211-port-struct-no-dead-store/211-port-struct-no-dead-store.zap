; Test: #port struct field reads must not be dead-store eliminated.
;
; Bug: when a local variable is overwritten by consecutive port reads,
; dead-store elimination incorrectly removed all but the last read.
; E.g. tmp=ACIA.STATUS / tmp=ACIA.CONTROL / ... collapsed to only the final read.
; Port reads have observable hardware side effects (clearing flags, advancing FIFOs, etc.)
; and must always be emitted even when the result is immediately overwritten.
;
; Verification strategy:
;   Part A — exact bug pattern (consecutive reads to same tmp).
;             Final tmp = last field; the .s file must contain all 4 LDA _CHIP instructions.
;   Part B — independent accumulation (reads interleaved with stores to acc).
;             Sum must equal $01+$02+$03+$04 = $0A, stored at $4200.

struct CHIP #port
    byte R1
    byte R2
    byte R3
    byte R4
end

; Pre-initialize the port memory locations with known values.
byte raw_r1 @$4211 = $01
byte raw_r2 @$4212 = $02
byte raw_r3 @$4213 = $03
byte raw_r4 @$4214 = $04

CHIP chip @$4211

byte result @$4200

proc main()
    byte tmp
    byte acc

    ; Part A: consecutive port reads into the same variable.
    ; Without the fix these three reads would be dead-store eliminated.
    tmp = chip.R1
    tmp = chip.R2
    tmp = chip.R3
    tmp = chip.R4

    ; Part B: accumulate each field independently to produce a verifiable sum.
    acc = 0
    tmp = chip.R1
    acc = acc + tmp
    tmp = chip.R2
    acc = acc + tmp
    tmp = chip.R3
    acc = acc + tmp
    tmp = chip.R4
    acc = acc + tmp

    result = acc
end
