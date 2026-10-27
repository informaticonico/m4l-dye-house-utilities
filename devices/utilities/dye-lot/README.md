# Dye Lot

Which key are you playing in? Dye Lot listens and tells Tannin. One of the Dye House Utilities, free, with Tannin, Dye Lot, Warp & Weft and Selvedge.

Put Dye Lot on the track you play (MIDI passes through untouched). It keeps a tally of the twelve pitch classes, each note counting by its velocity, and every bar the tally fades by Memory. At each bar it scores all 24 major and minor keys: the notes of the scale count once, the root twice, so A minor and C major (the same seven notes) are told apart by which root you lean on. The best is shown, with the two next best (the runners-up), each with how sure: its score over the best the tally could score (every note in the key's scale, its root the loudest), 0-100 %.

| Control | Range (default) | What it does |
| --- | --- | --- |
| Memory | 1, 2, 4, 8 bars (2 bars) | How long the tally takes to halve: short follows a change of key quickly, long ignores passing notes |
| SET | button | Sends the key shown to Tannin (`dyehouse_set`), which sets the whole house |
| AUTO | off / on (off) | SET at every bar |

**The panel** (v1.0b1, 330 px): the key heard large with how sure, the two runners-up under it with theirs, the twelve bars of what it heard (the key's notes green, its root outlined), SET, AUTO (lit while on), MEMORY as a value column (Live's own menu lies over it), and TANNIN NOW: the key Tannin holds, read as followers read it (`value dyehouse_key`, then `dyehouse_key`), *no Tannin* when there's none.

Push 3 shows one page, *Dye Lot* (Set, Auto, Memory).

It knows the twelve-note major and minor keys only; microtonal scales are set on Tannin. Nothing here has been checked in Live or on Push 3 yet.

## Building and testing

```sh
python3 build.py          # writes Dye Lot.amxd and checks its structure
python3 test/test_ui.py   # A minor and C major told apart; a change of key; a single quiet note ignored;
                          # the runners-up and how sure; SET and AUTO; with Tannin on the bus, SET changes the key
                          # of the house; TANNIN NOW
```

## Licence

MIT: see [LICENSE](../../../LICENSE).

Ableton, Live, Push and Max for Live are trademarks of Ableton AG. Max is a trademark of Cycling '74. This is an independent project, not affiliated with or endorsed by these companies.
