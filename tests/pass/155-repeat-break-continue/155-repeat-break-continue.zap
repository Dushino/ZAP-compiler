byte result @40000 = 0

proc main()
    byte i = 0
    byte j = 0
    byte k = 0
    byte cnt = 0

    ; --- check 1: break exits repeat before until-condition is reached ---
    ; without break the loop would run until i==10
    i = 0
    repeat
        i = i + 1
        if i == 3
            break
        end
    until i == 10
    if i == 3
        result = result + 1     ; 1: break stopped at i=3, not i=10
    end

    ; --- checks 2,3: continue jumps to until-condition, skipping code below it ---
    ; on j==2 iteration, continue skips cnt++ and re-tests until j==4
    j = 0
    cnt = 0
    repeat
        j = j + 1
        if j == 2
            continue
        end
        cnt = cnt + 1           ; runs on j=1,3,4 but NOT j=2
    until j == 4
    if j == 4
        result = result + 1     ; 2: loop ran to condition
    end
    if cnt == 3
        result = result + 1     ; 3: continue skipped one cnt++ (on j=2 iteration)
    end

    ; --- checks 4,5: break inside while-inside-repeat exits the while, not the repeat ---
    ; outer repeat runs twice; inner while breaks at k==3 each time
    i = 0
    j = 0
    repeat
        i = i + 1
        k = 0
        while k < 10
            k = k + 1
            if k == 3
                break           ; exits while only
            end
        end
        j = j + k               ; k==3 each time
    until i == 2
    if i == 2
        result = result + 1     ; 4: repeat ran twice (inner break didn't exit repeat)
    end
    if j == 6
        result = result + 1     ; 5: inner while broke at k=3 each outer iteration (3+3=6)
    end

    ; --- checks 6,7: continue inside while-inside-repeat continues the while, not the repeat ---
    ; inner while: k hits 1 (cnt++), 2 (continue, skip cnt++), 3 (cnt++), 4 (cnt++), then exits
    ; outer repeat runs twice → cnt = 3*2 = 6
    i = 0
    cnt = 0
    repeat
        i = i + 1
        k = 0
        while k < 4
            k = k + 1
            if k == 2
                continue        ; continues while (back to condition), skips cnt++
            end
            cnt = cnt + 1
        end
    until i == 2
    if i == 2
        result = result + 1     ; 6: outer repeat ran twice
    end
    if cnt == 6
        result = result + 1     ; 7: continue in while skipped one cnt++ per outer iter (3*2=6)
    end

    ; --- checks 8,9: break inside repeat-inside-while exits the repeat, not the while ---
    ; outer while runs 3 times; inner repeat breaks at k==2 each time
    i = 0
    j = 0
    while i < 3
        k = 0
        repeat
            k = k + 1
            if k == 2
                break           ; exits repeat only
            end
        until k == 10
        i = i + 1
        j = j + k               ; k==2 each time
    end
    if i == 3
        result = result + 1     ; 8: while ran 3 times (inner break didn't exit while)
    end
    if j == 6
        result = result + 1     ; 9: inner repeat broke at k=2 each iteration (2+2+2=6)
    end
end
