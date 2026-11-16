# SPDX-License-Identifier: GPL-3.0-or-later
# vangel engine - GNU Make 4
#
#   make [TARGET=host|sdl3] [V=1]  build the engine (default: host = the headless backend, for
#                                  tests; sdl3 = the player). The Amiga family comes later
#                                  (docs/engine-plan.md, M11).
#   make data SRC="..."            import the original game from your copy (../docs/game-data.md)
#                                  into ../resources/original/
#   make pack                      build the game pack ../build/<game>.pak from the imported game
#   make TARGET=host test          build and run the conformance tests
#   make clean                     remove ../build/
#   make data-clean                remove everything made from the game outside ../build/
#   make distclean                 clean + data-clean: only the committed files are left
#
# The engine (engine/: the scenario VM, the graphics, the text, the music layer) is built on
# lrvne (the submodule lrvne/: frame loop, screen, FM chip, PMD, mixer, fonts, packs,
# backends), which is compiled into it from source by its make fragment, lrvne/mk/lrvne.mk; a
# target is one of lrvne's (lrvne/mk/target/<TARGET>.mk).

# The one place a game is named: the game whose data `make data`, `make pack` and the tests work
# on (tools/games.py describes it; the engine and its program are the same for every game).
GAME ?= virginangel

LRVNE    := lrvne
TARGET   ?= host
BUILDROOT := ../build
BUILD    := $(BUILDROOT)/$(TARGET)
APP_NAME := vangel
APP_SRCS := $(sort $(wildcard engine/*.c engine/*/*.c))
APP_INCLUDES := -Iengine
# PMD 4.7g (the 26K setup) is lrvne's optional module; no voice clips: no Opus decoder
LRVNE_PMD  := 1
LRVNE_OPUS := 0
VG_VERSION := $(shell sed -n 's/^\#define VG_VERSION *"\(.*\)"/\1/p' engine/version.h)

ifeq ($(wildcard $(LRVNE)/mk/lrvne.mk),)
$(error the lrvne submodule is missing: git submodule update --init)
endif

.DEFAULT_GOAL := all
include $(LRVNE)/mk/lrvne.mk

.PHONY: all clean test
all: $(EXE)

clean:
	rm -rf $(BUILDROOT)

# ---------------------------------------------------------------------------------------------
# Conformance tests (host target). Every test compares the engine with data from the original
# code under emulation or a verified reference tool (tools/, ../re-tools/), never with its own
# output. tests/run.sh runs the data-free tests first; those that need the imported game are
# skipped with a note when it is missing. A test program is the engine without its program's
# description and main, on the test's own HAL (tests/test_hal.h).
# ---------------------------------------------------------------------------------------------
TEST_SRCS := $(sort $(wildcard tests/*.c))
TEST_EXES := $(patsubst tests/%.c,$(BUILD)/tests/%$(EXESUF),$(TEST_SRCS))
TEST_OBJS := $(filter-out $(BUILD)/engine/main.o $(BUILD)/engine/app.o,$(APP_OBJS)) \
             $(LRVNE_LIB_OBJS) \
             $(filter $(BUILD)/$(LRVNE)/backends/common/%,$(LRVNE_BACKEND_OBJS))
-include $(patsubst tests/%.c,$(BUILD)/tests/%.d,$(TEST_SRCS))

$(BUILD)/tests/%$(EXESUF): $(BUILD)/tests/%.o $(TEST_OBJS)
	@mkdir -p $(dir $@)
	@echo "  LINK  $@"
	$(Q)$(LRVNE_LD) $(OPT) -o $@ $< $(TEST_OBJS) $(LDLIBS)

test: $(TEST_EXES) $(EXE)
	$(Q)GAME=$(GAME) tests/run.sh $(BUILD)

# the original's results of the emulation checks, kept between runs
# (tests/refcache.py; REFCACHE=on|off|refresh|verify)
.PHONY: clean-refcache
clean-refcache:
	rm -rf $(BUILDROOT)/refcache

# ---------------------------------------------------------------------------------------------
# The game's data (../docs/game-data.md), which the repository does not carry.
#   make data SRC="zip-or-images ..."      (or LRVNE_MEDIA=<directories> make data)
# imports the game's media into ../resources/original/ (checked against
# ../resources/inventory.tsv) and unpacks M.EXE into ../resources/derived/.
# ---------------------------------------------------------------------------------------------
LRVNE_PY   := python3 -I
LRVNE_TOOL := $(LRVNE_PY) $(LRVNE)/tools/lrvne
.PHONY: data data-check
data:
	$(Q)GAME=$(GAME) $(LRVNE_PY) tools/gamedata.py import $(SRC)
data-check:
	$(Q)GAME=$(GAME) $(LRVNE_PY) tools/gamedata.py check

DATA_GENERATED := ../resources/original ../resources/derived
.PHONY: data-clean distclean
data-clean:
	rm -rf $(DATA_GENERATED)
distclean: clean data-clean

# ---------------------------------------------------------------------------------------------
# The pack: the kanji-ROM stand-in fonts (lrvne's xfont from the X11 bitmap fonts in
# lrvne/fonts/x11) and everything the engine needs from the original game (tools/mkpack.py).
# The same for every target.
# ---------------------------------------------------------------------------------------------
X11FONTS ?= $(LRVNE)/fonts/x11
ORIGINAL ?= ../resources/original
PAK      ?= $(BUILDROOT)/$(GAME).pak
.PHONY: pack
pack:
	$(Q)mkdir -p $(BUILDROOT)/fonts
	$(Q)$(LRVNE_TOOL) xfont --no-bold -o $(BUILDROOT)/fonts/ank8rom.xfnt $(X11FONTS)/8x16rk.bdf >/dev/null
	$(Q)$(LRVNE_TOOL) xfont --no-bold -o $(BUILDROOT)/fonts/k16.xfnt $(X11FONTS)/jiskan16.bdf >/dev/null
	$(Q)$(LRVNE_PY) tools/mkpack.py --game $(GAME) --original $(ORIGINAL) --fonts $(BUILDROOT)/fonts \
	    -o $(PAK)
