; Test comprehensive enum operations for the 6502 simulator
enum byte State
    INIT = 5
    START = 10
    RUNNING = 15
    STOPPED = 20
end

enum word BigState
    IDLE = 1000
    ACTIVE = 2000
    DONE = 3000
end

byte b_results[20] @40000
word w_results[20] @40030

proc main()
    ; byte combinations
    b_results[0] = State.INIT + State.START       ; 15
    b_results[1] = State.RUNNING - State.START    ; 5
    b_results[2] = State.INIT * 2                 ; 10
    b_results[3] = State.STOPPED / State.INIT     ; 4
    b_results[4] = State.RUNNING % 6              ; 3
    b_results[5] = State.START & 15               ; 10
    b_results[6] = State.INIT | 2                 ; 7
    b_results[7] = State.INIT ^ 3                 ; 6
    b_results[8] = State.INIT << 1                ; 10
    b_results[9] = State.STOPPED >> 1             ; 10
    b_results[10] = State.INIT == 5               ; 1
    b_results[11] = State.START != 10             ; 0
    b_results[12] = State.START < State.RUNNING   ; 1
    b_results[13] = State.STOPPED > State.START   ; 1
    b_results[14] = State.INIT <= 5               ; 1
    b_results[15] = State.RUNNING >= 10           ; 1
    b_results[16] = (State.INIT == 5) && (State.START == 10) ; 1
    b_results[17] = (State.INIT == 0) || (State.START == 10) ; 1
    b_results[18] = !(State.INIT == 0)            ; 1
    b_results[19] = ~State.INIT                   ; 250 (0xfa)

    ; word combinations
    w_results[0] = BigState.IDLE + 500            ; 1500
    w_results[1] = BigState.DONE - BigState.ACTIVE; 1000
    w_results[2] = BigState.IDLE * 2              ; 2000
    w_results[3] = BigState.DONE / 3              ; 1000
    w_results[4] = BigState.ACTIVE % 3            ; 2
    w_results[5] = BigState.IDLE & 1023           ; 1000
    w_results[6] = BigState.IDLE | 1              ; 1001
    w_results[7] = BigState.IDLE ^ 3              ; 1003
    w_results[8] = BigState.IDLE << 1             ; 2000
    w_results[9] = BigState.ACTIVE >> 1           ; 1000
    w_results[10] = BigState.IDLE == 1000         ; 1
    w_results[11] = BigState.ACTIVE != 2000       ; 0
    w_results[12] = BigState.IDLE < BigState.ACTIVE; 1
    w_results[13] = BigState.DONE > BigState.ACTIVE; 1
    w_results[14] = BigState.IDLE <= 1000         ; 1
    w_results[15] = BigState.ACTIVE >= 1000       ; 1
    w_results[16] = (BigState.IDLE == 1000) && (BigState.ACTIVE == 2000) ; 1
    w_results[17] = (BigState.IDLE == 0) || (BigState.ACTIVE == 2000)    ; 1
    w_results[18] = !(BigState.IDLE == 0)         ; 1
    w_results[19] = ~BigState.IDLE                ; 64535 (0xfc17)
end
