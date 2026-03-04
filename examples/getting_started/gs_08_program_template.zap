; Example: gs_08_program_template.zap
; Source: GETTING_STARTED.md, section "Your First Real Program Template" (lines 920-951)
;
; Demonstrates: complete program structure with init, update loop, main

; Global variables
byte state = 0
byte counter = 0

; Initialize everything
proc initialize()
    state = 1
    counter = 0
end

; Main game/app logic
proc update()
    counter = counter + 1
    if counter > 100
        state = 0
        counter = 0
    end
end

; Main entry point
proc main()
    initialize()
    while state == 1
        update()
    end
end
