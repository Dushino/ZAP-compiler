@echo off
rem python -m compiler ./tests/test_if_0.act > ./tests/test_if_0.s
rem python -m compiler ./tests/test_if_1_else.act  > ./tests/test_if_1_else.s



@echo off

for %%f in (./TESTS/*.act) do (
    echo Kompiluji %%f...
    python -m compiler "./TESTS/%%f" > "./TESTS/%%~nf.s"
)
echo Hotovo!
pause
