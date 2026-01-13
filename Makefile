# 65c02 experimental compiler

APPNAME=p1
LIBDIR=lib
SRC1DIR=src1
SRC2DIR=src2
OBJDIR=obj
BINDIR=out

USBDEVICE=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0

# compiler and linekr options
ZC   = python3 compiler.py
CL   = cl65
CC   = cc65
AS   = ca65
LD   = ld65
DA   = da65

# main
APPDIR 		=  $(APPNAME)
APPSRC1DIR 	=  $(APPDIR)/$(SRC1DIR)
APPSRC1 	=  $(APPSRC1DIR)/$(APPNAME).zap
APPSRC2DIR 	=  $(APPDIR)/$(SRC2DIR)
APPSRC 		=  $(APPSRC2DIR)/$(APPNAME).s
APPOBJDIR 	=  $(APPDIR)/$(OBJDIR)
APPOBJ 		=  $(APPOBJDIR)/$(APPNAME).o
APPBINDIR 	=  $(APPDIR)/$(BINDIR)
APPBIN 		:= $(APPBINDIR)/$(APPNAME)
LIBDIR      =  lib

ATARI_CPU = 6502
ATARI_AS_OPTS = -I $(LIBDIR) -t none --cpu $(ATARI_CPU) -g

SBC_CPU   = w65c02
SBC_AS_OPTS  = -I $(LIBDIR) -t none --cpu $(SBC_CPU) -g


# Rules
.PHONY:	all clean sbc atari tests


all: atari 

upload: sbc
	@./upload.sh $(BINDIR)/$(APPNAME).s19 $(USBDEVICE)

run: atari
	atari800 -basic $(APPBIN).com

atari: compile_atari
	$(AS) $(ATARI_AS_OPTS) $(LIBDIR)/atari/exehdr.s -o $(APPOBJDIR)/exehdr.o
	$(LD) -C cfg/my_atari.cfg $(APPOBJ) $(APPOBJDIR)/exehdr.o  -o $(APPBIN).com	
	dd if=$(APPBIN).com of=$(APPBIN).cut bs=6 skip=1
	$(DA) --cpu $(ATARI_CPU) --multi-pass --start-addr $4006 --comments 3 --hexoffs --verbose --verbose  $(APPBIN).cut > $(APPBIN).da65


compile_atari: 
	@mkdir -p $(APPSRC2DIR) $(APPOBJDIR) $(APPBINDIR)	
	$(ZC) -6502 $(APPSRC1) -o $(APPSRC)		
#	$(ZC) -6502 --peepholes $(APPSRC1) -o $(APPSRC)	
	$(AS) $(ATARI_AS_OPTS) $(APPSRC) -o $(APPOBJ)


upload: sbc

sbc: compile_sbc
	$(AS) $(SBC_AS_OPTS) $(LIBDIR)/atari/exehdr.s -o $(APPOBJDIR)/exehdr.o
	$(LD) -C cfg/my_sbc.cfg $(APPOBJ) -o $(APPBIN).com	
	$(DA) --cpu $(SBC_CPU) --multi-pass --start-addr $4006 --comments 3 --hexoffs --verbose --verbose  $(APPBIN).cut > $(APPBIN).da65

compile_sbc: 
	@mkdir -p $(APPSRC2DIR) $(APPOBJDIR) $(APPBINDIR)	
#	$(ZC) $(APPSRC1) -o $(APPSRC)	
	$(ZC) --peepholes $(APPSRC1) -o $(APPSRC)	
	$(AS) $(SBC_AS_OPTS) $(APPSRC) -o $(APPOBJ)


tests:
	@echo "=========================================="
	@echo "Running ZAP Compiler Test Suite"
	@echo "=========================================="
	@mkdir -p tests/pass tests/fail
	@pass_count=0; fail_count=0; error_count=0; \
	echo ""; \
	echo "Testing files that SHOULD PASS..."; \
	echo "------------------------------------------"; \
	for zapfile in tests/pass/*.zap; do \
		if [ -f "$$zapfile" ]; then \
			base=$$(basename $$zapfile .zap); \
			printf "%-30s" "$$base.zap: "; \
			if $(ZC) -6502 $$zapfile -o tests/pass/$$base.s >/dev/null 2>&1; then \
				echo "✓ PASS"; \
				pass_count=$$((pass_count + 1)); \
			else \
				echo "✗ FAIL (expected to pass but failed)"; \
				$(ZC) -6502 $$zapfile -o tests/pass/$$base.s 2>&1 | head -5; \
				error_count=$$((error_count + 1)); \
			fi; \
		fi; \
	done; \
	echo ""; \
	echo "Testing files that SHOULD FAIL..."; \
	echo "------------------------------------------"; \
	for zapfile in tests/fail/*.zap; do \
		if [ -f "$$zapfile" ]; then \
			base=$$(basename $$zapfile .zap); \
			printf "%-30s" "$$base.zap: "; \
			if $(ZC) -6502 $$zapfile -o tests/fail/$$base.s >/dev/null 2>&1; then \
				echo "✗ FAIL (expected to fail but passed)"; \
				error_count=$$((error_count + 1)); \
			else \
				echo "✓ PASS (correctly rejected)"; \
				fail_count=$$((fail_count + 1)); \
			fi; \
		fi; \
	done; \
	echo ""; \
	echo "=========================================="; \
	echo "Test Results Summary"; \
	echo "=========================================="; \
	echo "Should-pass tests: $$pass_count passed"; \
	echo "Should-fail tests: $$fail_count correctly rejected"; \
	echo "Errors: $$error_count"; \
	echo ""; \
	if [ "$$error_count" -eq 0 ]; then \
		echo "✓ All tests behaved as expected!"; \
		exit 0; \
	else \
		echo "✗ $$error_count test(s) behaved incorrectly"; \
		exit 1; \
	fi



# --------------------------------------------------------------------------
# Cleanup rules
clean:
	find $(APPOBJDIR)  -name *.o -type f -delete | true
	find $(APPBINDIR)  -name *.com -type f -delete | true
	find $(APPBINDIR)  -name *.cut -type f -delete | true
	find $(APPBINDIR)  -name *.da65 -type f -delete | true
	find $(APPSRC2DIR) -name *.s -type f -delete | true
	find $(APPSRC2DIR) -name *.inc -type f -delete | true
	find tests/pass -name *.s -type f -delete 2>/dev/null | true
	find tests/pass -name *.o -type f -delete 2>/dev/null | true
	find tests/fail -name *.s -type f -delete 2>/dev/null | true
	find tests/fail -name *.o -type f -delete 2>/dev/null | true


	
	


