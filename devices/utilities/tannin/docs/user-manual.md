# Tannin — User Manual

Oct 19, 2026 · @nichbuick

## Start here

<!-- generated: start tannin -->
1. **Set the key.** Drop Tannin on any MIDI track (MIDI passes through untouched). Pick **ROOT** and **SCALE**: click a value for its menu, or drag it. 27 scales, microtonal ones too.
2. **Point devices at it.** On Mordant, Logwood or Selvedge, set **Key** to **Tannin key**. **ON TANNIN KEY** shows what they play.
3. **Read the circle.** The root is filled in blue, the scale's other notes ringed. The line under it says how many notes the scale has.
4. **Or start from Live.** **LIVE'S KEY** shows Live's current scale. **FROM LIVE** copies it into Tannin, once, when you press it. Tannin never changes Live.
<!-- end of generated -->

The [map of the panel](#map-of-the-panel) shows what every part does.

## Welcome to Tannin

Tannin sets one key for the whole Dye House. Tannin fixes a mordant in the cloth; this fixes the key across a set. Choose a Root and a Scale (the family's 27, microtonal ones included) and every family device with its **Key** set to **Tannin key** plays in that key, wherever Live's own scale isn't in force. Change it, on Push or with a clip's automation, and the whole set follows at once. Tannin also shows Live's current scale and tuning, and never changes either.


What makes it special:

- **Microtonal, everywhere.** 19-EDO, Bohlen-Pierce, the partials scales and, from Oct 1, 5, 7, 9, 15, 17, 22 and 24-EDO reach every following device, not just 12-note keys.
- **No setup.** No routing, no mapping: devices find Tannin by themselves, anywhere in the set (made to run on Push 3 standalone too).
- **Late joiners.** A device switched to Tannin key later still gets the key straight away.

This manual covers Tannin v1.0.1.

| Item | Requirement |
| --- | --- |
| Ableton Live | Live 12 with Max for Live (Suite, or Standard with the Max for Live add-on) |
| Max | The version bundled with Live, no extra packages |
| Operating system | macOS or Windows, as supported by your Live version |
| Controller (optional) | Push 3 (its standalone mode not yet tested), or any MIDI controller |

## Map of the panel


<!-- generated: map tannin -->
| | Area | What it does |
| --- | --- | --- |
| 1 | **ROOT and SCALE** | The key for the whole set: click a value for its menu, drag it, or map it. |
| 2 | **The circle** | The key on the twelve notes, C at the top: the root filled, the scale's notes ringed; a microtonal scale as its steps. Under it, how many notes the scale has. |
| 3 | **LIVE'S KEY** | Live's current scale, in Live's own words, and whether its Scale Mode is on. |
| 4 | **FROM LIVE** | Copies Live's current scale into Root and Scale, once, when you press it. Beside it, what devices on Live key play. |
| 5 | **TUNING** | Live 12.1's tuning system, when one is loaded. |
| 6 | **ON TANNIN KEY** | The key every device set to Tannin key plays (a warning instead while a second Tannin is in the set). |
<!-- end of generated -->

## Quick start and the panel

One page with pictures first: **Tannin - Quick Start.pdf**, beside this manual in the download, numbers the parts to touch and gives three things to try.

1. Drag the `Dye House Utilities` folder anywhere into your User Library (for example its top level) and open it in Live's browser: Tannin is in its own folder there.
2. Drop it on any MIDI track. MIDI passes through it untouched, so it can share a track with anything.
3. Set **Root** and **Scale**, then set **Key** to **Tannin key** on the devices that should play in it.

| Control | What it does |
| --- | --- |
| Root | C to B |
| Scale | Chromatic, Major, Minor, Dorian, Phrygian, Pentatonic minor and major, Partials, Stretched, Bohlen-Pierce, 19-EDO, then Live 12's Mixolydian, Lydian, Locrian, Harmonic and Melodic Minor, Harmonic Major, Phrygian Dominant, Whole Tone and Minor Blues; then equal divisions of the octave: 5-EDO (slendro-like), 7-EDO (Thai-like), 9, 15, 17 (the Arabic 17-tone), 22 (shruti-like) and 24-EDO (quarter tones) |
| ROOT and SCALE | Each shown as a column: its name on a blue label, the value large, a bar under it marking where it sits among the choices. Click the value for the menu, drag it, or map it, as any of Live's controls |
| The circle | The key on a circle of the twelve notes, C at the top: the root filled in blue, the scale's other notes ringed. A microtonal scale (Partials, Stretched, Bohlen-Pierce, the EDOs) is drawn as its steps, a dot each around one turn from the root, a turn being the interval it repeats at |
| The line under it | How many notes the scale has: "7 notes an octave", "19 notes an octave", "13 steps a tritave" (Bohlen-Pierce), "8 steps every 12.6 st" (Stretched) |
| LIVE'S KEY | Live's current scale, the one above the tracks, in Live's own words: purple, or amber when it isn't one of the family's scales. At its right, whether Live's Scale Mode is on |
| FROM LIVE | Copies Live's current scale into Tannin's Root and Scale, once, when you press it. Beside it, what devices set to **Live key** play: their own key (Scale Mode off), this (on), or Chromatic from Live's root (on, with a scale the family doesn't have) |
| TUNING | Live 12.1's tuning system, if one is loaded (see below) |
| ON TANNIN KEY | The key every device on Tannin key plays, in blue. While a second Tannin is in the set, the warning in amber instead: keep one |

Which devices have the **Key** choice: Mordant, Logwood and Selvedge (Root and Scale). More of the family's devices get it as they're released.

| Key | The device plays |
| --- | --- |
| **Own key** (default) | Its own Root and Scale |
| **Live key** | Live's scale (below); with none in force, its own key, and it says *no Live scale* |
| **Tannin key** | Tannin's key; with no Tannin in the set, its own key, and it says *no Tannin* |

With Live or Tannin chosen, a device never changes its own Root and Scale: they grey out, keep their values and automation, and are there again when you choose Own. A line on the device reads the key it's playing: blue for Tannin's, purple for Live's, amber when Live's scale isn't one of the family's.

### Tannin and Live's own scales


Live 12 has scales of its own. Each clip can have one, and the one above the tracks, Live's **current scale**, is the scale of the clip you selected last: it isn't one key for the whole set. Live's own scale-aware devices (Arpeggiator, Chord, Pitch, Random, Scale) take the scale of the clip playing on their track. **Live key** does the same: the scale of the Session clip playing on the device's track, if that clip's Scale Mode is on; otherwise Live's current scale, if its Scale Mode is on.

So which to choose? **Live key** when your clips carry scales and you work in the Session with twelve-note keys: nothing else to set up. **Tannin key** for what Live's scales can't do:

- **The microtonal scales** (Partials, Stretched, Bohlen-Pierce and the EDOs): Live's scales can't hold them.
- **One key for the whole set**, on every track at once, including returns, audio tracks and devices inside racks, and in the Arrangement, where Live key falls back to the last selected clip's scale.
- **Key changes you automate:** Tannin's Root and Scale can be automated; clip scales can't.
- **Dye Lot's SET**, which changes Tannin.

Tannin never writes to Live and never changes by itself: writing Live's current scale would change whichever clip happens to be selected. It shows Live's current scale instead, and **FROM LIVE** copies it into Tannin when you ask (one undo step, yours).

Live's scales that the family has (Major, Minor, the modes, both pentatonics, Harmonic and Melodic Minor, Harmonic Major, Phrygian Dominant, Whole Tone, Minor Blues, Chromatic) arrive as themselves. The others (Hungarian Minor, Hirajoshi and so on) play as Chromatic from Live's root, so no note is missing, and the readout turns amber to say so.

### Live's tuning systems


Live 12.1 can load a tuning system (a `.ascl` or Scala file) for the whole set, and retunes Live's instruments and MPE instruments to it. Tannin shows its name when one is loaded. The family's microtonal scales work differently: they send their own pitch bend. Don't use both at once: with a Live tuning loaded, keep the family's devices on twelve-note scales, or Live and the device will both retune the same notes. A later update may read Live's tuning directly (see `docs/keys-and-live.md`).

## Use cases

### 1. One key for the whole set


Tannin on the first MIDI track, Key set to Tannin everywhere: change key once, before a take.

### 2. Key changes in the arrangement

Automate Tannin's Root in a clip or the arrangement: at the chorus, everything following moves up a tone together.

### 3. With Dye Lot


Play a few bars; Dye Lot hears the key and its SET button changes Tannin. Every following device lands in it.

## Push 3, automation and reference

Root, Scale and FROM LIVE are on Push's **Tannin** page; Root and Scale can be automated like any control. Tannin's panel shows Live's current scale, which Push's own Scale settings change.

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| A device doesn't follow | Its Key must be set to Tannin key |
| Tannin says another Tannin is in the set | Keep one: two take turns, and the last change wins |
| Tannin's key has no effect on a device | Its Key is set to Live key (its readout is purple) or Own key: choose Tannin key |
| Readout amber, every note plays | Live's scale isn't one of the family's 27, so it plays as Chromatic |
| A device stopped following when the set's only Tannin was deleted | As intended: it plays its own key until a Tannin or a Live scale is back |

### Specifications

| | |
| --- | --- |
| Device type | Max for Live MIDI effect |
| Parameters | 3, all automatable, 1 Push page |
| Scales | The family's 27 (Live 12's included) |
| Latency | None |
| Push 3 standalone | Made to run there (no external files; the circle is a drawing script packed inside the device, which Push 3 doesn't show), not yet tested there |

### Credits and licence

Tannin is designed and published by @nichbuick, as part of the Tincture family. Questions, bug reports and ideas: an issue on this repository, or a message through [Gumroad](https://nichbuick.gumroad.com).

Ableton, Live, Push and Max for Live are trademarks of Ableton AG. Max is a trademark of Cycling '74. Tannin is an independent product and is not affiliated with or endorsed by these companies.

## What's new

### 1.0.1 (Oct 26, 2026)

Fixed: every part of the panel now shows a line in Live's Info View when you hover it, the drawings and labels too (they showed only the object's kind). It comes with a one-page Quick Start with pictures. Your saved sets open and sound as before.

### 1.0 (Oct 23, 2026)

The first release.
