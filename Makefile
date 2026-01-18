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
SIM  = 6502_simulator

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
TEST_REPORT_FILE = tests_report.txt
TEST_REPORT = tests/$(TEST_REPORT_FILE)
PASS_ROOT ?= tests/pass
FAIL_ROOT ?= tests/fail

ATARI_CPU = 6502
ATARI_AS_OPTS = -I $(LIBDIR) -t none --cpu $(ATARI_CPU) -g

SBC_CPU   = w65c02
SBC_AS_OPTS  = -I $(LIBDIR) -t none --cpu $(SBC_CPU) -g


# Rules
.PHONY:	all clean sbc atari tests test


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


tests: clean
	@echo "=========================================="
	@echo "Running ZAP Compiler Test Suite"
	@echo "=========================================="
	@mkdir -p $(PASS_ROOT) $(FAIL_ROOT)
	@rm -f $(TEST_REPORT)
	@pass_count=0; fail_count=0; error_count=0; \
	echo ""; \
	echo "Testing files that SHOULD PASS..."; \
	echo "------------------------------------------"; \
	for zapfile in $$(find $(PASS_ROOT) -name '*.zap' -type f 2>/dev/null | sort); do \
		if [ -f "$$zapfile" ]; then \
			base=$$(basename $$zapfile .zap); \
			dir=$$(dirname $$zapfile); \
			ref_file="$${dir}/$${base}.ref"; \
			variant_pass=0; variant_fail=0; variant_errors=""; \
			for variant_flags in "" "--peepholes" "-6502" "-6502 --peepholes"; do \
				variant_name=$$(echo "$$variant_flags" | sed 's/ /_/g' | sed 's/^$$/_default/'); \
				output_file="$${dir}/$${base}$${variant_name}.s"; \
				obj_file="$${dir}/$${base}$${variant_name}.o"; \
				exehdr_obj="$${dir}/$${base}$${variant_name}_exehdr.o"; \
				bin_file="$${dir}/$${base}$${variant_name}.com"; \
				cut_file="$${dir}/$${base}$${variant_name}.cut"; \
				dis_file="$${dir}/$${base}$${variant_name}.dis65"; \
				txt_file="$${dir}/$${base}$${variant_name}.txt"; \
				sim_config_file="$${dir}/$${base}.json"; \
				if echo "$$variant_flags" | grep -q -- "-6502"; then \
					as_cpu="6502"; \
				else \
					as_cpu="65c02"; \
				fi; \
				if echo "$$variant_flags" | grep -q -- "-6502"; then \
					da_cpu="6502"; \
				else \
					da_cpu="65c02"; \
				fi; \
				echo "$$zapfile" >> $(TEST_REPORT); \
				if [ -z "$$variant_flags" ]; then \
					echo "$(ZC) \"$$zapfile\" -o \"$$output_file\"" >> $(TEST_REPORT); \
				else \
					echo "$(ZC) $$variant_flags \"$$zapfile\" -o \"$$output_file\"" >> $(TEST_REPORT); \
				fi; \
				if ! $(ZC) $$variant_flags $$zapfile -o $$output_file >> $(TEST_REPORT) 2>&1; then \
					variant_errors="$$variant_errors [ZAP_ERROR:$$variant_name]"; \
					variant_fail=$$((variant_fail + 1)); \
					echo "ZAP compiler failed" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "---------------------------------------------------------------" >> $(TEST_REPORT); \
					continue; \
				fi; \
				echo "$(AS) -I $(LIBDIR) -t none --cpu $$as_cpu -g \"$$output_file\" -o \"$$obj_file\"" >> $(TEST_REPORT); \
				if ! $(AS) -I $(LIBDIR) -t none --cpu $$as_cpu -g $$output_file -o $$obj_file >> $(TEST_REPORT) 2>&1; then \
					variant_errors="$$variant_errors [CA65_ERROR:$$variant_name]"; \
					variant_fail=$$((variant_fail + 1)); \
					echo "ca65 assembler failed" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "---------------------------------------------------------------" >> $(TEST_REPORT); \
					continue; \
				fi; \
				echo "$(AS) -I $(LIBDIR) -t none --cpu $$as_cpu -g $(LIBDIR)/atari/exehdr.s -o \"$$exehdr_obj\"" >> $(TEST_REPORT); \
				if ! $(AS) -I $(LIBDIR) -t none --cpu $$as_cpu -g $(LIBDIR)/atari/exehdr.s -o $$exehdr_obj >> $(TEST_REPORT) 2>&1; then \
					variant_errors="$$variant_errors [CA65_ERROR:exehdr-$$variant_name]"; \
					variant_fail=$$((variant_fail + 1)); \
					echo "ca65 assembler failed on exehdr" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "---------------------------------------------------------------" >> $(TEST_REPORT); \
					continue; \
				fi; \
				echo "$(LD) -C cfg/my_atari.cfg \"$$obj_file\" \"$$exehdr_obj\" -o \"$$bin_file\"" >> $(TEST_REPORT); \
				if ! $(LD) -C cfg/my_atari.cfg $$obj_file $$exehdr_obj -o $$bin_file >> $(TEST_REPORT) 2>&1; then \
					variant_errors="$$variant_errors [LD65_ERROR:$$variant_name]"; \
					variant_fail=$$((variant_fail + 1)); \
					echo "ld65 linker failed" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "---------------------------------------------------------------" >> $(TEST_REPORT); \
					continue; \
				fi; \
				echo "$(DA) --cpu $$da_cpu --multi-pass --comments 3 --hexoffs --verbose --verbose \"$$cut_file\"" >> $(TEST_REPORT); \
				if ! $(DA) --cpu $$da_cpu --multi-pass --info cfg/my_atari.info --comments 3 --hexoffs --verbose --verbose $$bin_file > $$dis_file 2>&1; then \
					variant_errors="$$variant_errors [DA65_ERROR:$$variant_name]"; \
					variant_fail=$$((variant_fail + 1)); \
					echo "da65 disassembler failed" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "---------------------------------------------------------------" >> $(TEST_REPORT); \
					continue; \
				fi; \
				echo "if $(SIM) --cpu $$as_cpu --config $$sim_config_file --verbose --dump-file $$txt_file $$bin_file >> $(TEST_REPORT)" 2>&1 >> $(TEST_REPORT); \
				if $(SIM) --cpu $$as_cpu --config $$sim_config_file --verbose --dump-file $$txt_file $$bin_file >> $(TEST_REPORT) 2>&1; then \
					:; \
				else \
					variant_errors="$$variant_errors [SIM_ERROR:$$variant_name]"; \
					variant_fail=$$((variant_fail + 1)); \
					echo "Simulation failed" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "---------------------------------------------------------------" >> $(TEST_REPORT); \
					continue; \
				fi; \
				if [ ! -f "$$ref_file" ]; then \
					variant_errors="$$variant_errors [NO_REF_FILE]"; \
					variant_fail=$$((variant_fail + 1)); \
					echo "cmp \"$$ref_file\" \"$$txt_file\"" >> $(TEST_REPORT); \
					echo "Reference file not found" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "---------------------------------------------------------------" >> $(TEST_REPORT); \
					continue; \
				fi; \
				echo "cmp \"$$ref_file\" \"$$txt_file\"" >> $(TEST_REPORT); \
				if ! cmp -s $$ref_file $$txt_file; then \
					variant_errors="$$variant_errors [OUTPUT_MISMATCH:$$variant_name]"; \
					variant_fail=$$((variant_fail + 1)); \
					echo "Output does not match reference file" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "" >> $(TEST_REPORT); \
					echo "---------------------------------------------------------------" >> $(TEST_REPORT); \
					continue; \
				fi; \
				variant_pass=$$((variant_pass + 1)); \
				echo "" >> $(TEST_REPORT); \
				echo "" >> $(TEST_REPORT); \
				echo "---------------------------------------------------------------" >> $(TEST_REPORT); \
			done; \
			printf "%-30s" "$$base.zap: "; \
			if [ $$variant_fail -eq 0 ]; then \
				echo "✓ PASS (all 4 variants)"; \
				pass_count=$$((pass_count + 1)); \
			else \
				echo "✗ FAIL ($$variant_fail/4 variants failed)$$variant_errors"; \
				error_count=$$((error_count + 1)); \
			fi; \
		fi; \
	done; \
	echo ""; \
	echo "Testing files that SHOULD FAIL..."; \
	echo "------------------------------------------"; \
	for zapfile in $$(find $(FAIL_ROOT) -name '*.zap' -type f 2>/dev/null | sort); do \
		if [ -f "$$zapfile" ]; then \
			base=$$(basename $$zapfile .zap); \
			dir=$$(dirname $$zapfile); \
			printf "%-30s" "$$base.zap: "; \
			# Also log compiler output for should-fail tests to the report \
			if $(ZC) -6502 $$zapfile -o $${dir}/$${base}.s >> $(TEST_REPORT) 2>&1; then \
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
		echo " ✅ All tests behaved as expected!"; \
		exit 0; \
	else \
		echo "❌ $$error_count test(s) behaved incorrectly"; \
		exit 1; \
	fi


# Single-directory test run: e.g. `make test ./pass/015-for-loop`
# Additional goal after `test` is treated as directory under tests/.
ifeq ($(filter test,$(MAKECMDGOALS)),test)
TEST_PATH_RAW := $(firstword $(filter-out test,$(MAKECMDGOALS)))
TEST_SUBDIR := $(patsubst tests/%,%,$(patsubst ./%,%,$(TEST_PATH_RAW)))

# Prevent make from treating the extra argument as a real target
ifneq ($(strip $(TEST_PATH_RAW)),)
.PHONY: $(TEST_PATH_RAW)
$(TEST_PATH_RAW):
	@:
endif

test: PASS_ROOT := $(if $(TEST_SUBDIR),tests/$(TEST_SUBDIR),tests/pass)
test: FAIL_ROOT := $(if $(TEST_SUBDIR),tests/.empty_fail,tests/fail)
endif

test: tests



# --------------------------------------------------------------------------
# Cleanup rules
clean:
	find $(APPOBJDIR)  -name '*.o' -type f -delete 2>/dev/null | true
	find $(APPBINDIR)  -name '*.com' -type f -delete 2>/dev/null | true
	find $(APPBINDIR)  -name '*.cut' -type f -delete 2>/dev/null | true
	find $(APPBINDIR)  -name '*.da65' -type f -delete 2>/dev/null | true
	find $(APPSRC2DIR) -name '*.s' -type f -delete 2>/dev/null | true
	find $(APPSRC2DIR) -name '*.inc' -type f -delete 2>/dev/null | true
	find tests -name '$(TEST_REPORT_FILE)' -type f -delete 2>/dev/null | true
	find tests/pass -name '*.s' -type f -delete 2>/dev/null | true
	find tests/pass -name '*.o' -type f -delete 2>/dev/null | true
	find tests/pass -name '*.com' -type f -delete 2>/dev/null | true
	find tests/pass -name '*.cut' -type f -delete 2>/dev/null | true
	find tests/pass -name '*.txt' -type f -delete 2>/dev/null | true
	find tests/pass -name '*.dis65' -type f -delete 2>/dev/null | true
	find tests/fail -name '*.s' -type f -delete 2>/dev/null | true
	find tests/fail -name '*.o' -type f -delete 2>/dev/null | true
	
	
	


