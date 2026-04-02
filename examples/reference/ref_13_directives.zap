; Example: ref_13_directives.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Directives" (lines 2579-2633)
;
; Demonstrates: .define, .ifdef/.ifndef/.else/.endif, .info/.warning
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; --- Preprocessor Directives ---
.define DEBUG

.ifdef DEBUG
    .info "Debug mode enabled"
.else
    .define OPTIMIZED
.endif

; --- Diagnostic Directives ---
.info "ref_13_directives.zap compiling"

proc main()
    byte x = 0
.ifdef DEBUG
    x = 1   ; Debug-only code
.endif
end
