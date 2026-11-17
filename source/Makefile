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
#   make e2e-routes                play the end-to-end check's plans on the engine again
#   make text-template             every string of the game for translators (derived game data,
#                                  ../build/tl/template.tsv; ../docs/translation.md)
#   make text-check                check every translation in ../text/translation/
#   make TARGET=sdl3 dist          the player's archive ../build/sdl3/vangel-<version>-<host>.tar.gz
#   make dist-src                  the source archive ../build/vangel-<version>-src.tar.gz
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

# lrvne's replay of a log of the real PMD.COM (tests/check_pmd.py), built from lrvne's source
LRV_TEST_PMD := $(BUILD)/tests/lrv_test_pmd$(EXESUF)
LRV_TEST_PMD_OBJS := $(LRVNE_LIB_OBJS) $(filter $(BUILD)/$(LRVNE)/backends/common/%,$(LRVNE_BACKEND_OBJS))
-include $(BUILD)/$(LRVNE)/tests/test_pmd.d
$(LRV_TEST_PMD): $(BUILD)/$(LRVNE)/tests/test_pmd.o $(LRV_TEST_PMD_OBJS)
	@mkdir -p $(dir $@)
	@echo "  LINK  $@"
	$(Q)$(LRVNE_LD) $(OPT) -o $@ $< $(LRV_TEST_PMD_OBJS) $(LDLIBS)

test: $(TEST_EXES) $(LRV_TEST_PMD) $(EXE)
	$(Q)GAME=$(GAME) tests/run.sh $(BUILD)

# the routes of the end-to-end check (tests/check_vm.py): the plans of tests/e2e/explore.py
# played on the engine again, into tests/e2e/routes (commit them; make test checks that the
# engine still plays them so)
.PHONY: e2e-routes
e2e-routes: $(BUILD)/tests/test_game$(EXESUF)
	$(Q)$(LRVNE_PY) tests/e2e/explore.py $(BUILD)/tests/test_game$(EXESUF) $(PAK)

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
	    $(foreach t,$(PACK_TEXT),--text $(t)) -o $(PAK)

# ---------------------------------------------------------------------------------------------
# Translations (../docs/translation.md): ../text/translation/vangel_<lang>.tsv, keys and text
# only. `make pack` packs every one of them (PACK_TEXT="pl=FILE ..." instead); the template
# and the reading copies hold the game's Japanese, derived data that stays in ../build/ (never
# in the repository).
# ---------------------------------------------------------------------------------------------
TL_DIR    ?= ../text/translation
PACK_TEXT ?= $(foreach f,$(sort $(wildcard $(TL_DIR)/vangel_*.tsv)),$(patsubst vangel_%.tsv,%,$(notdir $(f)))=$(f))
.PHONY: text-template text-check
text-template:
	$(Q)$(LRVNE_PY) tools/tl.py template $(PAK) $(BUILDROOT)/tl/template.tsv
text-check:
	$(Q)for t in $(PACK_TEXT); do \
	    $(LRVNE_PY) tools/tl.py check $${t#*=} --pak $(PAK) || exit 1; \
	done

# ---------------------------------------------------------------------------------------------
# Release archives. The version is engine/version.h's (the release is tagged v<version>).
# `make TARGET=sdl3 dist`: $(BUILD)/vangel-<version>-<name>.tar.gz, which unpacks to
# VANGEL/{vangel, ReadMe.txt, LICENSE, LICENSE.ymfm}: the stripped executable, the player's
# ReadMe (dist/ReadMe.txt, @VERSION@ replaced) and the licences of what is in the executable.
# The pack is not in it: it is the game's data, which the player builds from their own copy
# (the ReadMe says how). <name> is the target's (lrvne's LRVNE_DIST_NAME).
# `make dist-src`: the committed tree at HEAD with the lrvne submodule's (git archive; the
# repository holds no game data).
# ---------------------------------------------------------------------------------------------
DIST_README ?= dist/ReadMe.txt
DIST_STRIP  ?= strip
DIST        := $(BUILD)/vangel-$(VG_VERSION)-$(LRVNE_DIST_NAME).tar.gz
DISTDIR     := $(BUILD)/dist
SRC_NAME    := vangel-$(VG_VERSION)
SRCDIST     := $(BUILDROOT)/srcdist
# no local user or group names in the archive (GNU tar / bsdtar spell it differently)
TAR_ANON    := $(if $(shell tar --version 2>/dev/null | grep GNU),--owner=0 --group=0 --numeric-owner,--uid 0 --gid 0 --uname '' --gname '')
.PHONY: dist dist-src
dist: $(EXE)
	$(Q)test -n "$(LRVNE_DIST_NAME)" || { echo "dist: no release archive for TARGET=$(TARGET) (TARGET=sdl3)"; exit 1; }
	$(Q)rm -rf $(DISTDIR) $(DIST)
	$(Q)mkdir -p $(DISTDIR)/VANGEL
	$(Q)cp $(EXE) $(DISTDIR)/VANGEL/
	$(if $(DIST_STRIP),$(Q)$(DIST_STRIP) $(DISTDIR)/VANGEL/vangel$(EXESUF))
	$(Q)sed 's/@VERSION@/$(VG_VERSION)/g' $(DIST_README) >$(DISTDIR)/VANGEL/ReadMe.txt
	$(Q)cp ../LICENSE $(DISTDIR)/VANGEL/LICENSE
	$(Q)cp $(LRVNE)/third_party/ymfm/LICENSE $(DISTDIR)/VANGEL/LICENSE.ymfm
	@echo "  TAR   $(DIST)"
	$(Q)cd $(DISTDIR) && tar $(TAR_ANON) -czf $(abspath $(DIST)) VANGEL
	$(Q)tar -tzvf $(DIST)
dist-src:
	@echo "  TAR   $(BUILDROOT)/$(SRC_NAME)-src.tar.gz"
	$(Q)rm -rf $(SRCDIST)
	$(Q)mkdir -p $(SRCDIST)
	$(Q)git -C .. archive --format=tar --prefix=$(SRC_NAME)/ HEAD | tar -x -C $(SRCDIST)
	$(Q)git -C $(LRVNE) archive --format=tar --prefix=$(SRC_NAME)/source/lrvne/ HEAD | tar -x -C $(SRCDIST)
	$(Q)cd $(SRCDIST) && tar $(TAR_ANON) -czf ../$(SRC_NAME)-src.tar.gz $(SRC_NAME)
	$(Q)rm -rf $(SRCDIST)
