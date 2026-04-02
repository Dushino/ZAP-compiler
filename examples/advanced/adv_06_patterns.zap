; Example: adv_06_patterns.zap
; Source: ADVANCED_TOPICS.md, section "Advanced Patterns" (lines 1158-1291)
;
; Demonstrates: state machine, event handling, object pooling, message passing
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.



; --- State Machine ---
const byte STATE_INIT = 0
const byte STATE_PLAY = 1
const byte STATE_PAUSE = 2
const byte STATE_OVER = 3

byte game_state = STATE_INIT

proc initialize_game()
    ; Stub
end

proc update_game()
    ; Stub
end

proc check_pause()
    ; Stub
end

proc check_game_over()
    ; Stub
end

proc check_unpause()
    ; Stub
end

proc show_game_over()
    ; Stub
end

proc update_state()
    switch game_state
        case STATE_INIT
            initialize_game()
            game_state = STATE_PLAY
            break

        case STATE_PLAY
            update_game()
            check_pause()
            check_game_over()
            break

        case STATE_PAUSE
            check_unpause()
            break

        case STATE_OVER
            show_game_over()
            break
    end
end

; --- Event Handling ---
byte event_collision = 0
byte event_powerup = 0
byte event_death = 0

proc on_collision()
    ; Stub
end

proc on_powerup()
    ; Stub
end

proc on_death()
    ; Stub
end

proc handle_events()
    if event_collision
        on_collision()
        event_collision = 0
    end

    if event_powerup
        on_powerup()
        event_powerup = 0
    end

    if event_death
        on_death()
        event_death = 0
    end
end

; --- Object Pooling ---
const byte MAX_SPRITES = 10

byte sprite_x[MAX_SPRITES]
byte sprite_y[MAX_SPRITES]
byte sprite_active[MAX_SPRITES]
byte sprite_count = 0

proc spawn_sprite(byte x, byte y)
    if sprite_count < MAX_SPRITES
        sprite_x[sprite_count] = x
        sprite_y[sprite_count] = y
        sprite_active[sprite_count] = 1
        sprite_count = sprite_count + 1
    end
end

proc update_sprites()
    byte i = 0
    for i = 0 to sprite_count
        if sprite_active[i]
            sprite_y[i] = sprite_y[i] + 1

            if sprite_y[i] > 191
                sprite_active[i] = 0
            end
        end
    end
end

; --- Message Passing ---
const byte MAX_MESSAGES = 5
byte message_queue[MAX_MESSAGES]
byte message_count = 0

proc process_message(byte msg)
    ; Stub
end

proc send_message(byte msg)
    if message_count < MAX_MESSAGES
        message_queue[message_count] = msg
        message_count = message_count + 1
    end
end

proc process_messages()
    byte i = 0
    for i = 0 to message_count
        process_message(message_queue[i])
    end
    message_count = 0
end

; --- Frame Timing ---
byte frame_counter = 0

proc do_expensive_operation()
    ; Stub
end

proc do_fast_operation()
    ; Stub
end

proc game_update()
    frame_counter = frame_counter + 1

    ; Every 30 frames
    if frame_counter == 30
        do_expensive_operation()
        frame_counter = 0
    end

    ; Do fast updates every frame
    do_fast_operation()
end

proc main()
    update_state()
    handle_events()
    spawn_sprite(100, 50)
    spawn_sprite(120, 60)
    update_sprites()
    send_message(1)
    send_message(2)
    process_messages()
    game_update()
end
