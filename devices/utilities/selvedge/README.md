# Selvedge

A tuner for the Dye House's scales, microtonal ones included. Selvedge is the finished edge of a cloth; this checks the edge of a note. One of the Dye House Utilities, free, with Tannin, Dye Lot, Warp & Weft and Selvedge.

Put it on any audio (a hardware synth, a resonator, a voice); audio passes through untouched. It tracks the pitch and shows how far it is from the nearest step of the scale, which step that is, and the step's nearest twelve-note name with its offset: on A 19-EDO a note near the fourth step reads *step 4 of 19* and *B3 -11 cents* (that step sits 11 cents under B3).

| Control | Range (default) | What it does |
| --- | --- | --- |
| Root | C to B (A) | The scale's root |
| Scale | the family's 27 scales (Minor) | Microtonal ones included |
| Key | Own key, Live key, Tannin key (Own key) | Tune to its own Root and Scale, Live's scale, or Tannin's |

**The panel** (v1.0b1, 380 px): TUNER, the step large with its nearest twelve-note name and cents and the Hz, the cents meter (flat, green within 5 cents), and the scale's steps as a strip (a cell a step, as wide as the step, the nearest lit, the root outlined, the twelve names above where they fall); SCALE, Root, Scale and Key as value columns (Live's own menus lie over them), Key in its source's colour (blue Tannin, purple Live, amber a Live scale the family lacks), Root and Scale pale while another key is played, and PLAYS, the key measured against and its own.

Push 3 shows one page, *Selvedge* (Root, Scale, Key).

**Inside.** Max's `fzero~` tracks the pitch; the gen~ codebox (`dsp.py`) finds the nearest step of the scale, counted from the Root in octave 3 (C3 = 60; it matters for scales that don't repeat at the octave, such as Bohlen-Pierce), and outputs the cents from it, the step's number and the step's exact pitch. Nothing here has been checked in Live or on Push 3 yet.

## Building and testing

```sh
python3 build.py          # writes gen/selvedge.genexpr and Selvedge.amxd, and checks its structure
python3 test/test_dsp.py  # the codebox (lib/genexpr.py) and the readouts (lib/maxsim.py)
python3 test/test_ui.py   # the panel: the readout (step 4 of 19, B3 -11 cents), the meter, the steps strip, the
                          # columns and the key's colours, a set reopening
```

## Licence

MIT: see [LICENSE](../../../LICENSE).

Ableton, Live, Push and Max for Live are trademarks of Ableton AG. Max is a trademark of Cycling '74. This is an independent project, not affiliated with or endorsed by these companies.
