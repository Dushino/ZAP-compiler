; Test: Shift-add multiply correctness for constants with >= 2 set bits
;
; Bug: The 16-bit shift-add used INC TMP4+1 per carry, which fails when
; TMP4+1 is non-zero from a prior carry and the next shift should double it.
; Example: 40*16 = 640 ($0280) was computed as 384 ($0180) because shift 4
; set TMP4+1=1 (correct for 16y overflow), but shift 5 of TMP3=0 had
; carry=0 so no INC — yet TMP4+1 should have doubled to 2.
;
; The fix uses ASL TMP3 / ROL TMP3+1 for proper 16-bit shifting, and a
; full 16-bit add for each partial term.
;
; Expected at $0200:
;   $0200-$0201: $0280 = 640  = 40 * 16  (two-bit constant, carry doubles)
;   $0202-$0203: $0488 = 1160 = 40 * 29  (max screen row, both shifts carry)
;   $0204-$0205: $00C0 = 192  = 24 * 8   (another two-bit constant)
;   $0206-$0207: $0780 = 1920 = 24 * 80  (word-sized index)

word result1 @$0200 = 0
word result2 @$0202 = 0
word result3 @$0204 = 0
word result4 @$0206 = 0

proc main()
    byte y16 = 16
    byte y29 = 29
    byte y8  = 8

    result1 = 40 * y16   ; 640  = $0280  was $0180 before fix
    result2 = 40 * y29   ; 1160 = $0488  was $0388 before fix
    result3 = 24 * y8    ; 192  = $00C0  (8+16) * 8 = sanity check
    result4 = 24 * 80    ; 1920 = $0780  constant fold, not shift-add
end
