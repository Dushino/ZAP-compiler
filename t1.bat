@echo tests\pass\041-incbin\041-incbin.zap 
python compiler.py "tests\pass\041-incbin\041-incbin.zap" -o "tests\pass\041-incbin\041-incbin_default.s" 
ca65 -I lib -t none --cpu 65c02 -g "tests\pass\041-incbin\041-incbin_default.s" -o "tests\pass\041-incbin\041-incbin_default.o" 
ca65 -I lib -t none --cpu 65c02 -g lib\atari\autostart.s -o "tests\pass\041-incbin\041-incbin_default_autostart.o" 
ca65 -I lib -t none --cpu 65c02 -g lib\atari\exehdr.s -o "tests\pass\041-incbin\041-incbin_default_exehdr.o" 
ld65 -C cfg\my_atari.cfg "tests\pass\041-incbin\041-incbin_default.o" "tests\pass\041-incbin\041-incbin_default_exehdr.o" "tests\pass\041-incbin\041-incbin_default_autostart.o" -o "tests\pass\041-incbin\041-incbin_default.com" 
6502_simulator.exe --cpu 65c02 --config tests\pass\041-incbin\041-incbin.json --verbose --dump-file "tests\pass\041-incbin\041-incbin_default.txt" "tests\pass\041-incbin\041-incbin_default.com" 
