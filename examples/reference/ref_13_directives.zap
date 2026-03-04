; Example: ref_13_directives.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Directives" (lines 2579-2633)
;
; Demonstrates: .define, .ifdef/.ifndef/.else/.endif, .info/.warning

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
