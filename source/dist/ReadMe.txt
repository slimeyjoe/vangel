vangel @VERSION@
================

A portable engine for Virgin Angel, the visual novel Crystal Soft published for the NEC
PC-9801 in 1995. vangel runs the original scenario, text, pictures and FM music unmodified and
reproduces the PC-98 release; translations of the text can be added to it.

Adults only: the game contains explicit sexual scenes, some of them non-consensual.

This archive holds only the engine. It contains none of the game.


What you need
-------------

* SDL 3 (the shared library: libSDL3 from your package manager, Homebrew or MacPorts).
* The game pack, virginangel.pak, built from your own copy of the PC-98 release with the
  tools in vangel's source: `make data SRC=...` then `make pack` (docs/game-data.md in the
  source). Put virginangel.pak next to the vangel program, or name it with --pak.


Playing
-------

    ./vangel                     play
    ./vangel --help              all options

Options: --fullscreen, --window WxH, --scale integer|aspect|fit|stretch, --volume 0..100,
--no-audio, --storage DIR, --pak FILE, --view (browse the pictures), --lang TAG (the
language of the text, e.g. pl, when the pack has that translation; ja is the original).
The language given is remembered: the next start without --lang uses it.

At the start the game asks, as on the PC-98, whether to use the mouse: Y or N.

The keyboard is the PC-98's: any key or the left button turns a page of text; in a menu the
cursor keys Up and Down move, Return chooses, and the mouse chooses what it points at with the
left button. In the music mode Up and Down choose a song, Return or Space play it, Esc (or the
right button) leaves.

  F11 or Alt+Return   fullscreen on/off
  F12                 next scaling mode
  Ctrl+Shift+R        reset: the game starts again (saves are kept)
  Shift+Esc           quit at once


Saves
-----

Saves are kept as the original's file game.dat (three slots) in
$XDG_DATA_HOME/vangel/virginangel (default ~/.local/share/vangel/virginangel), or in the
directory given with --storage. A GAME.DAT from a PC-98 copy of the game can be put there (as
game.dat) and is used as it is.


Licence
-------

vangel is free software under the GNU General Public License, version 3 or later (LICENSE).
Its source is available where you got this archive. The FM sound is made by ymfm (Aaron
Giles, BSD 3-Clause licence: LICENSE.ymfm).
