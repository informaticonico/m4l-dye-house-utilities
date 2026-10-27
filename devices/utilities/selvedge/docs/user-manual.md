# Selvedge — User Manual

Oct 19, 2026 · @nichbuick

## Start here

<!-- generated: start selvedge -->
1. **Play one note.** Drop Selvedge on an audio track or after an instrument (the audio passes through untouched) and play one note at a time.
2. **Pick the scale.** **ROOT** and **SCALE**: click for the menu, or drag.
3. **Or follow the house.** **KEY**: *Tannin key* or *Live key* reads against Tannin's or Live's scale. **PLAYS** shows the key it measures against.
4. **Read the step.** **step k of N**: the nearest step of the scale (1 is the root), lit in **THE SCALE'S STEPS** below. Beside it, that step's nearest 12-note name and how far the step is from it.
5. **Tune it.** The meter shows how far the note is from that step, -50 to +50 cents: + is sharp, - is flat; green within 5 cents.
<!-- end of generated -->

The [map of the panel](#map-of-the-panel) shows what every part does.

## Welcome to Selvedge

Selvedge is a tuner for the Dye House's scales, microtonal ones included. The selvedge is the finished edge of a cloth; Selvedge checks the edge of a note. Put it on any audio (a hardware synth, a resonator, a voice) and it shows how far the note is from the nearest step of the scale, which step that is, and where that step sits against the 12 notes you know.


What makes it special:

- **Any scale.** 19-EDO, Bohlen-Pierce and the partials scales are measured against their own steps, not the nearest piano key.
- **Knows its step.** On A 19-EDO, "step 4 of 19" and "B3 -11 cents" tell you exactly which note of the scale you're on, and that this step sits 11 cents under B3.
- **Checks against the house's key:** set Key to Tannin or Live and it reads against that.

This manual covers Selvedge v1.0.1.

| Item | Requirement |
| --- | --- |
| Ableton Live | Live 12 with Max for Live (Suite, or Standard with the Max for Live add-on) |
| Max | The version bundled with Live, no extra packages |
| Operating system | macOS or Windows, as supported by your Live version |
| Controller (optional) | Push 3 (its standalone mode not yet tested), or any MIDI controller |

## Map of the panel


<!-- generated: map selvedge -->
| | Area | What it does |
| --- | --- | --- |
| 1 | **The step** | Which step of the scale the note is nearest, that step's nearest 12-note name and its cents, and the pitch heard. |
| 2 | **The meter** | How far the note is from that step, -50 to +50 cents; green within 5. |
| 3 | **The scale's steps** | A cell a step, as wide as the step, from the root; the nearest lit, the twelve note names above where they fall. |
| 4 | **ROOT and SCALE** | The scale to measure against; pale while KEY isn't Own. |
| 5 | **KEY** | Own key, Live key or Tannin key, in its source's colour. |
| 6 | **PLAYS** | The key it measures against now, and its own Root and Scale. |
<!-- end of generated -->

## Quick start and the panel

One page with pictures first: **Selvedge - Quick Start.pdf**, beside this manual in the download, numbers the parts to touch and gives three things to try.

1. Drag the `Dye House Utilities` folder anywhere into your User Library (for example its top level) and open it in Live's browser: Selvedge is in its own folder there.
2. Drop it on an audio track (or after an instrument). Audio passes through untouched.
3. Set **Root** and **Scale** (or choose **Live key** or **Tannin key**), play one note at a time, and read the display.

| Readout or control | What it shows or does |
| --- | --- |
| Step k of N | Which step of the scale the note is nearest (1 is the root), large; under it, the key it measures against |
| Name and cents | That step's nearest 12-note name, and how far the step itself is from it (on A 19-EDO the fourth step is *B3 -11 cents*) |
| Hz | The pitch heard |
| The meter | How far the note is from the nearest step, -50 to +50 cents: + is sharp, - is flat; green within 5 cents |
| The scale's steps | A cell for each step, as wide as the step is, from the root (outlined in its key's colour); the nearest lit; the twelve note names above where they fall; under the cells the root's number, the nearest's and the last's |
| ROOT, SCALE | The scale to measure against, each a column (click it for the menu, drag it, or map it). Scales that don't repeat at the octave (Bohlen-Pierce) count from the Root in octave 3 (C3 = 60, as Live). Pale while Key isn't Own: they stay as they are |
| KEY | Own key, Live key (Live's scale where its Scale Mode is on, the clip playing on this track first) or Tannin key, in its source's colour: blue for Tannin's, purple for Live's, amber for a Live scale the family lacks (read as Chromatic) |
| PLAYS | The key it measures against, in the same colour (*no Tannin*, *no Live scale* when there's none: then its own), and its own Root and Scale |

The pitch tracker follows one note at a time. For a chord, it reports the strongest pitch.

## Use cases

### 1. Tuning a hardware synth to 19-EDO


Scale 19-EDO, play the synth's lowest note of each step and tune it until the cents read 0.

### 2. Checking a resonator


Put Selvedge after a resonator tuned to Tannin's key: ringing notes read 0 cents on their steps.

### 3. Singing in Bohlen-Pierce


Read the step and cents while you find the unfamiliar intervals.

## Push 3, automation and reference

Root, Scale and Key are on Push's **Selvedge** page.

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| It says *listening* | The signal is too quiet or too noisy to track; play one clean note |
| The step jumps between two | The note sits halfway between steps; that's what the cents show |
| Octave errors on low notes | The tracker can lock onto a harmonic; play a little higher |

### Specifications

| | |
| --- | --- |
| Device type | Max for Live audio effect |
| Parameters | 3, all automatable, 1 Push page |
| Pitch tracking | Max's fzero~ |
| Scales | The family's 27 (Live 12's included) |
| Latency | None: audio passes through |
| Push 3 standalone | Not yet tested; made to run there: no external files; its meter and the steps strip are drawing scripts packed inside the device, which Push 3 doesn't show |

### Credits and licence

Selvedge is designed and published by @nichbuick, as part of the Tincture family. Questions, bug reports and ideas: an issue on this repository, or a message through [Gumroad](https://nichbuick.gumroad.com).

Ableton, Live, Push and Max for Live are trademarks of Ableton AG. Max is a trademark of Cycling '74. Selvedge is an independent product and is not affiliated with or endorsed by these companies.

## What's new

### 1.0.1 (Oct 26, 2026)

Fixed: every part of the panel now shows a line in Live's Info View when you hover it, the drawings and labels too (they showed only the object's kind). It comes with a one-page Quick Start with pictures. Your saved sets open and sound as before.

### 1.0 (Oct 23, 2026)

The first release.
