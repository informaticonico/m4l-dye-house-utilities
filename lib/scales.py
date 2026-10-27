"""The family's scales, shared by every device that tunes to them (Mordant, other devices, ...).

Each is (name, steps in semitones above the root, period in semitones: where the
steps repeat). The partials scales and Bohlen-Pierce don't repeat at the octave.
The first eleven are Mordant's originals; the rest are Live 12's own common scales,
so FOLLOW can take Live's Scale (lib/kit.py). New scales go at the end: a saved
set stores the menu's index.
"""

import math


def _partials(stretch):
    """As Mordant: overtones 8..15 of a note, as semitones above it; stretch widens every interval."""
    return [round(12 * stretch * math.log2(k / 8), 4) for k in range(8, 16)], round(12 * stretch, 4)


SCALES = [
    ("Chromatic", list(range(12)), 12),
    ("Major", [0, 2, 4, 5, 7, 9, 11], 12),
    ("Minor", [0, 2, 3, 5, 7, 8, 10], 12),
    ("Dorian", [0, 2, 3, 5, 7, 9, 10], 12),
    ("Phrygian", [0, 1, 3, 5, 7, 8, 10], 12),
    ("Pent Min", [0, 3, 5, 7, 10], 12),
    ("Pent Maj", [0, 2, 4, 7, 9], 12),
    ("Partials", *_partials(1.0)),
    ("Stretched", *_partials(1.05)),
    ("Bohlen-P", [round(k * 1901.955 / 1300, 4) for k in range(13)], round(19.01955, 4)),
    ("19-EDO", [round(k * 12 / 19, 4) for k in range(19)], 12),
    # Live 12's scales (Scale Mode), as Live names them
    ("Mixolydian", [0, 2, 4, 5, 7, 9, 10], 12),
    ("Lydian", [0, 2, 4, 6, 7, 9, 11], 12),
    ("Locrian", [0, 1, 3, 5, 6, 8, 10], 12),
    ("Harm Minor", [0, 2, 3, 5, 7, 8, 11], 12),
    ("Mel Minor", [0, 2, 3, 5, 7, 9, 11], 12),
    ("Harm Major", [0, 2, 4, 5, 7, 8, 11], 12),
    ("Phryg Dom", [0, 1, 4, 5, 7, 8, 10], 12),
    ("Whole Tone", [0, 2, 4, 6, 8, 10], 12),
    ("Minor Blues", [0, 3, 5, 6, 7, 10], 12),
    # equal divisions of the octave (E22, Oct 1: Elmyra 2's scale cards, and more): 5 slendro-like,
    # 7 Thai-like, 9, 15, 17 (the Arabic 17), 22 (shruti-like) and 24 (quarter tones)
] + [(f"{n}-EDO", [round(k * 12 / n, 4) for k in range(n)], 12) for n in (5, 7, 9, 15, 17, 22, 24)]


def mask(steps):
    """A twelve-tone scale as Live's scale_intervals would give it, as one number: bit k set for
    each step k semitones above the root."""
    return sum(1 << int(k) for k in steps)


# Live's scale (its scale_intervals' mask) -> the family's scale; Live scales not here play Chromatic
LIVE = {mask(st): i for i, (_, st, per) in enumerate(SCALES)
        if per == 12 and all(float(k).is_integer() for k in st)}


def degree(scale, d):
    """Semitones from the root to scale degree d (any integer, negative too)."""
    _, steps, period = SCALES[scale]
    return steps[d % len(steps)] + period * (d // len(steps))


# the scales off the semitone grid (steps between semitones, or a period other than the octave)
MICROTONAL = [i for i, (_, steps, period) in enumerate(SCALES)
              if period != 12 or any(abs(x - round(x)) > 1e-6 for x in steps)]


def live_tuning_code(sc="sc"):
    """gen~: with a Live tuning system loaded (Param livetun, lib/mpe.py's tuning_watch), a
    microtonal scale steps back to Chromatic (0): Live retunes the notes itself, so the synth's own
    microtonal steps would tune them twice. Twelve-note scales stay, and follow Live's tuning."""
    cond = " || ".join(f"{sc} == {i}" for i in MICROTONAL)
    return f"if (livetun > 0.5 && ({cond})) {{\n\t{sc} = 0;\n}}\n"
