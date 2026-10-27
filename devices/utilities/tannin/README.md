# Tannin

One key for the whole set, microtonal scales included. Tannin fixes a mordant in the cloth; this fixes the key across a set. One of the Dye House Utilities, free, with Tannin, Dye Lot, Warp & Weft and Selvedge.

Put Tannin anywhere, on any MIDI track (MIDI passes through untouched), and set its Root and Scale. Every family device whose **Key** menu is set to *Tannin key* plays in that key; the others play their own key, or Live's.

| Control | Range (default) | What it does |
| --- | --- | --- |
| Root | C to B (A) | The key's root |
| Scale | the family's 27 scales (Minor) | Major and minor modes, pentatonics, Live 12's scales, and the microtonal ones (Partials, Stretched, Bohlen-P, 19-EDO) |
| FROM LIVE | button | Copies Live's current scale (the one above the tracks) into Root and Scale: one undo step, yours |

**The panel** (v1.0b1, 330 px): Root and Scale as value columns on a blue card (Live's own menus lie over them, so a click, a drag, a map or automation reach each), the key on a circle (any scale's steps), LIVE'S KEY in Live's purple (amber when the family lacks Live's scale) with whether Scale Mode is on, FROM LIVE and what devices on *Live key* play beside it; TUNING, Live 12.1's tuning system when one is loaded; ON TANNIN KEY, the key every follower plays, where a warning shows instead while a second Tannin is in the set (two would take turns). Push 3 shows one page, *Tannin* (Root, Scale, From Live).

**Tannin never writes to Live and never changes by itself**: only you, FROM LIVE, or Dye Lot's SET change it.

**On the family bus** ([`lib/kit.py`](../../../lib/kit.py)): every change goes out as `root scale` on `dyehouse_key`, and is kept in `value dyehouse_key` so a device that starts following later still gets it. A `root scale` arriving on `dyehouse_set` (Dye Lot's SET) changes Tannin's own menus, which then send it on. As Tannin leaves the set it sends `gone`, so followers go back to their own key; if another Tannin is still in the set, that one sends its key again (and keeps it in the value), so followers play its key.

Nothing here has been checked in Live or on Push 3 yet (`verify/tannin.md`).

## Building and testing

```sh
python3 build.py          # writes Tannin.amxd and checks its structure
python3 test/test_ui.py   # the key on load, on change and for late followers; the columns; Dye Lot's SET; Live's scale shown,
                          # never written; FROM LIVE; the tuning system; a second Tannin; MIDI through
```

## Licence

MIT: see [LICENSE](../../../LICENSE).

Ableton, Live, Push and Max for Live are trademarks of Ableton AG. Max is a trademark of Cycling '74. This is an independent project, not affiliated with or endorsed by these companies.
