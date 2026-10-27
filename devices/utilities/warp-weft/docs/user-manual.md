# Warp & Weft — User Manual

Oct 19, 2026 · @nichbuick

## Start here

### Warp, on the track you play

<!-- generated: start warp -->
1. **Pick a cable.** Drop Warp on the track you play, after what makes the notes (Mordant, Push's pads, a clip) and before the instrument. Leave **CABLE** on A.
2. **Keep or pass on.** **THRU** on: this track keeps playing its own instrument too. Off: the notes only go down the cable.
3. **Add a Weft.** Drop **Weft** on another MIDI track, before an instrument, on the same cable. Play: both tracks sound. **SENDING** lights and names the notes held.
4. **Watch each note.** The keyboard lights the notes going through; each held note shows its **B**end, **P**ressure and **T**imbre.
<!-- end of generated -->

### Weft, on the track that listens

<!-- generated: start weft -->
1. **Pick the cable.** Put a **Warp** on the track you play. Drop Weft on another MIDI track, before an instrument, and choose the Warp's cable in **CABLE** (A to start). Play: both tracks sound.
2. **Check the sender.** **THE SENDER** says who is on the cable: *Warp A: playing* with the notes held, *Warp A: quiet*, *no Warp on A*, or *2 Warps on A* (both play here). This track's own MIDI plays as well.
3. **Watch each note.** The keyboard lights the notes arriving; each held note shows its **B**end, **P**ressure and **T**imbre, as its own channel carries it.
<!-- end of generated -->

The [map of the panel](#map-of-the-panel) shows what every part does.

## Welcome to Warp & Weft

Warp & Weft are cables between tracks for MIDI and MPE. The warp is the threads held on the loom, the weft the threads woven through them. **Warp** goes on a track that plays (Push's pads, Mordant, a MIDI clip) and sends everything it hears down a cable; **Weft** goes on any other track and plays what arrives. Any number of Wefts can listen to one cable.



What makes it special:

- **MPE survives.** Each note travels with its own channel, pitch bend, pressure and controllers, whole, so notes and their expression never get mixed up.
- **One performance, several synths.** Layer two Logwoods, a pad under a lead, from one set of pads, each on its own track with its own effects.
- **No routing menus.** Pick a cable, A to D; it is made to work on Push 3 standalone too.

This manual covers Warp & Weft v1.0.1.

| Item | Requirement |
| --- | --- |
| Ableton Live | Live 12 with Max for Live (Suite, or Standard with the Max for Live add-on) |
| Max | The version bundled with Live, no extra packages |
| Operating system | macOS or Windows, as supported by your Live version |
| Controller (optional) | Push 3 (MPE; its standalone mode not yet tested), any MPE controller, or any MIDI keyboard |

## Map of the panel

### Warp


<!-- generated: map warp -->
| | Area | What it does |
| --- | --- | --- |
| 1 | **CABLE** | A, B, C or D: the cable the notes go down (SENDS CABLE A says it at the top right). |
| 2 | **THRU** | On: this track keeps playing its own instrument too. Off: the notes only go down the cable. |
| 3 | **SENDING** | A light while notes are held on the cable, how many, and their names. |
| 4 | **The keyboard** | Three octaves: the notes going through, lit. |
| 5 | **Each note** | A slot for each held note: its pitch bend, pressure and timbre, as its own channel carries them. |
<!-- end of generated -->

### Weft


<!-- generated: map weft -->
| | Area | What it does |
| --- | --- | --- |
| 1 | **CABLE** | A, B, C or D: the cable it plays (PLAYS CABLE A says it at the top right). |
| 2 | **THE SENDER** | Who is on its cable: a Warp playing or quiet, none, or two; the notes held. The track's own MIDI plays as well. |
| 3 | **The keyboard** | Three octaves: the notes arriving, lit. |
| 4 | **Each note** | A slot for each held note: its pitch bend, pressure and timbre. |
<!-- end of generated -->

## Quick start and the panel

One page with pictures first: **Warp - Quick Start.pdf** and **Weft - Quick Start.pdf**, beside this manual in the download, numbers the parts to touch and gives three things to try.

1. Drag the `Dye House Utilities` folder anywhere into your User Library (for example its top level) and open it in Live's browser: Warp and Weft are each in their own folder there.
2. On the track you play, drop **Warp** (after anything that makes the notes, such as Mordant, and before the instrument). Leave its Cable on A.
3. On another MIDI track, drop **Weft** before an instrument, Cable A. Play: both tracks sound.

| Device | Control | What it does |
| --- | --- | --- |
| Both | CABLE | A · B · C · D, the one chosen lit: one control, Live's own, so a click, Push, a map or automation choose it. The card names it too (*SENDS CABLE A*, *PLAYS CABLE A*) |
| Both | The keyboard | Three octaves, from the C under the lowest note held (C2 while none is): the notes going through, lit |
| Both | Each note | A slot for each held note (the first four; more show as *+2* in the last slot): its name over three bars, its pitch bend (from the middle), pressure and timbre (CC 74), each as its own channel carries it |
| Warp | THRU | On: this track keeps playing its own instrument too. Off: the notes only go down the cable. The line under it says which |
| Warp | SENDING | A light while notes are held on the cable, how many, and their names |
| Weft | THE SENDER | Who is on its cable: *Warp A: playing* (with the notes held and their names), *Warp A: quiet* (a Warp is there, nothing held), *no Warp on A*, or *2 Warps on A* (both play here). Notes from another family device sending on the cable read *cable A: playing*. The track's own MIDI still plays as well |

What travels: notes (with their velocity and note-offs), pitch bend (all 14 bits), channel pressure and every controller, each on the channel it was played on.

## Use cases

### 1. Layering synths from Push


Warp on a Logwood track, THRU on; Weft on a second Logwood track. Every pad plays both, each note bending and swelling on both.

### 2. One sequencer, two voices


Mordant then Warp on the Weld track; a Weft before Logwood on another track: the same pattern plays the drum and the bass, each through its own effects.

### 3. Splitting a performance

Several Warps on different cables let one set of tracks feed several listeners; a Weft only hears its own cable.

## Push 3, automation and reference

Cable and Thru are on Push's **Warp** page, Cable on the **Weft** page.

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| The Weft is silent | Same cable on both? Is the Warp's track playing (armed, or a clip running)? |
| Notes double on the first track | That's THRU: turn it off to send only down the cable |
| Two Warps on one cable | Both are heard, mixed (the Weft says *2 Warps on A*). Give each its own cable |
| The Weft says *no Warp on A* | No Warp in the set is on that cable: choose the Warp's cable on the Weft, or put a Warp on it |
| Program changes don't arrive | Only notes, pitch bend, pressure and controllers travel (prototype) |

### Specifications

| | |
| --- | --- |
| Device type | Two Max for Live MIDI effects |
| Parameters | Warp 2 on 1 Push page; Weft 1 on 1 Push page; all automatable |
| Cables | 4 (A-D), any number of Wefts each |
| Latency | None added |
| Push 3 standalone | Not yet tested; made to run there: no external files; the cable selector, the words, the keyboard and the expression bars are drawing scripts packed inside the devices, which Push 3 doesn't show |

### Credits and licence

Warp & Weft are designed and published by @nichbuick, as part of the Tincture family. Questions, bug reports and ideas: an issue on this repository, or a message through [Gumroad](https://nichbuick.gumroad.com).

Ableton, Live, Push and Max for Live are trademarks of Ableton AG. Max is a trademark of Cycling '74. Warp & Weft are independent products and are not affiliated with or endorsed by these companies.

## What's new

### 1.0.1 (Oct 26, 2026)

Fixed: every part of the panel now shows a line in Live's Info View when you hover it, the drawings and labels too (they showed only the object's kind). It comes with a one-page Quick Start with pictures. Your saved sets open and sound as before.

### 1.0 (Oct 23, 2026)

The first release.
