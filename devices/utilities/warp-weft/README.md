# Warp & Weft

MIDI and MPE cables between tracks. One of the Dye House Utilities, free, with Tannin, Dye Lot, Warp & Weft and Selvedge.

- **Warp** (the sender) goes on the track that plays: Push 3's pads, Mordant, anything. Everything it hears (notes, per-note pitch bend, pressure and controllers, each on its own channel) goes down cable A, B, C or D. **THRU** (on) also lets it through on its own track.
- **Weft** (the receiver) goes on another track, before the instrument. It plays what arrives on its cable, mixed with that track's own MIDI. Any number of Wefts can listen to one cable: one Push performance, several synths.

| Device | Control | Range (default) | What it does |
| --- | --- | --- | --- |
| Warp | Cable | A-D (A) | The cable it sends on |
| | THRU | off / on (on) | Its own track keeps the MIDI too |
| Weft | Cable | A-D (A) | The cable it plays |

Push 3 shows one page each (*Warp*: Cable, Thru; *Weft*: Cable).

**The panel** (v1.0b1, 300 px each): the family cable selector, A · B · C · D, the chosen one lit (one live.tab, Cable, as the menu was: [`lib/panelg.py`](../../../lib/panelg.py)'s `cable_tab`); a keyboard of three octaves with the held notes lit; a slot for each held note with its pitch bend, pressure and timbre. Warp shows THRU and SENDING (the notes held, by name). Weft shows THE SENDER: *Warp A: playing* or *quiet*, *no Warp on A*, *2 Warps on A*.

The cables are the family bus ([`lib/kit.py`](../../../lib/kit.py)): `note p v ch`, `bend v ch`, `press v ch` and `cc v n ch`, whole messages, so a note and its expression never interleave. Each Warp keeps how many Warps are on each cable in `value dyehouse_warps_X` (one more as it loads or moves onto X, one fewer as it leaves X or the set) and sends `warps n` down the cable when that changes; a Weft reads the value as it loads or changes cable. Another device's KEYS listens to a cable too (it drops `warps`, as the probes' cable listeners do). Nothing here has been checked in Live or on Push 3 yet.

## Building and testing

```sh
python3 build.py          # writes Warp.amxd and Weft.amxd and checks their structure
python3 test/test_ui.py   # a note with its bend, pressure and timbre into every Weft on the cable; other cables
                          # don't hear it; THRU; the Weft's own MIDI plays too; the cable selector; the words, the
                          # keyboard and each note's expression; THE SENDER as Warps load, move and are deleted
```

## Licence

MIT: see [LICENSE](../../../LICENSE).

Ableton, Live, Push and Max for Live are trademarks of Ableton AG. Max is a trademark of Cycling '74. This is an independent project, not affiliated with or endorsed by these companies.
