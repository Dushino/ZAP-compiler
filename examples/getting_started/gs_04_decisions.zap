; Example: gs_04_decisions.zap
; Source: GETTING_STARTED.md, section "Making Decisions" (lines 350-464)
;
; Demonstrates: if/else, comparison operators, logical operators, nested conditions

byte game_state = 0    ; 0=menu, 1=playing, 2=paused, 3=over

proc check_age(byte age)
    if age >= 18
        ; Adult code
    else
        ; Minor code
    end
end

proc game_logic(byte level)
    if level == 1
        ; Easy level
    end
    if level < 5
        ; Early levels
    end
    if level > 9
        ; Hard levels
    end
end

proc enter_dungeon(byte level, byte health)
    if level >= 5 && health > 50
        ; Can enter
    end
end

proc is_ready(byte stamina, byte magic)
    if stamina > 20 || magic > 20
        ; Ready to fight
    end
end

proc complex_logic(byte a, byte b)
    if a > 10
        if b < 5
            ; a > 10 AND b < 5
        end
    end
end

proc update_game()
    if game_state == 0
        ; Show menu
    end
    if game_state == 1
        ; Update gameplay
    end
    if game_state == 2
        ; Show pause screen
    end
    if game_state == 3
        ; Show game over
    end
end

proc main()
    check_age(20)
    game_logic(3)
    enter_dungeon(6, 80)
    is_ready(30, 10)
    complex_logic(15, 3)
    update_game()
end
