# The Dye House Utilities

Five free Max for Live devices for Ableton Live 12 and Push 3, and the Python that builds them. Nothing here is
edited in Max: each device's patch, its drawings and its gen~ code are written by its `build.py`, and checked by
tests that run the patch, the drawings and the gen~ code offline, without Live or Max.

| Device | What it does |
| --- | --- |
| [Tannin](devices/utilities/tannin/) | One key for the whole house |
| [Dye Lot](devices/utilities/dye-lot/) | Hears the key you play in; sends it to Tannin |
| [Warp](devices/utilities/warp-weft/) | Sends a track's notes and MPE down a cable |
| [Weft](devices/utilities/warp-weft/) | Plays what arrives on a cable |
| [Selvedge](devices/utilities/selvedge/) | A tuner for any of the family's scales |

Tannin, Dye Lot and Selvedge share one key across a set (the family bus, `lib/kit.py`); Warp and Weft send a track's
notes and per-note expression down a cable to another track.

## Building and testing

Python 3.8 or newer, nothing to install.

```sh
python3 devices/utilities/tannin/build.py        # writes Tannin.amxd and checks its structure
python3 devices/utilities/tannin/test/test_ui.py # its patch, run in lib/maxsim.py
python3 run_tests.py                             # every device built (as committed, byte for byte) and tested
```

`lib/` holds the shared code these devices use: `m4l.py` writes a patch and its parameters, `maxsim.py` runs one,
`jsrun.py` runs the drawing scripts, `genexpr.py` runs gen~ code, and `annotations.py`, `frozen.py`, `genlint.py`, `kit.py`, `kittest.py`, `livesizes.py`, `panelg.py`, `scales.py`, `visual.py` the rest.

## Using the devices

Download them, with their manuals, from The Dye House; or build them here and drag the `.amxd` into Live. The
manuals are in each device's `docs/`.

## Licence

MIT: see [LICENSE](LICENSE). Issues are welcome; pull requests by invitation ([CONTRIBUTING.md](CONTRIBUTING.md)).

Ableton, Live, Push and Max for Live are trademarks of Ableton AG. Max is a trademark of Cycling '74. This is an independent project, not affiliated with or endorsed by these companies.
