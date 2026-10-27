# Dye Lot — User Manual

Oct 19, 2026 · @nichbuick

## Start here

<!-- generated: start dye-lot -->
1. **Play.** Drop Dye Lot on the MIDI track you play, before the instrument (the MIDI passes through untouched). After a bar or two **KEY HEARD** shows the key that fits best, how sure, and two **RUNNERS-UP**.
2. **Send it.** **SET** sends the key to Tannin: every device on **Key** Tannin key plays in it.
3. **Or let it follow.** **AUTO** sends it every bar by itself, so the house follows whatever you play. Lit while on.
4. **Choose how long it remembers.** **MEMORY**: a note's weight halves every 1, 2, 4 or 8 bars. Short follows a key change quickly; long isn't swayed by passing notes.
5. **Check Tannin.** **TANNIN NOW** shows the key Tannin holds, in Tannin's blue.
<!-- end of generated -->

The [map of the panel](#map-of-the-panel) shows what every part does.

## Welcome to Dye Lot

Dye Lot tells you which key you're playing in. A dye lot is a batch dyed together, so every piece matches. Put it on a track, play for a few bars, and Dye Lot shows the major or minor key that fits best; one press sends it to Tannin, which sets the whole house.


What makes it special:

- **Listens to the root you lean on.** A minor and C major share seven notes; Dye Lot tells them apart by the note you come back to.
- **Follows you.** Older bars fade, so when the song changes key, the suggestion follows within a few bars.
- **One press to the whole house** through Tannin.

This manual covers Dye Lot v1.0.1.

| Item | Requirement |
| --- | --- |
| Ableton Live | Live 12 with Max for Live (Suite, or Standard with the Max for Live add-on) |
| Max | The version bundled with Live, no extra packages |
| Operating system | macOS or Windows, as supported by your Live version |
| Controller (optional) | Push 3 (its standalone mode not yet tested), or any MIDI controller |

## Map of the panel


<!-- generated: map dye-lot -->
| | Area | What it does |
| --- | --- | --- |
| 1 | **The key** | The major or minor key that fits best, checked every bar, and how sure it is. |
| 2 | **RUNNERS-UP** | The two keys that fit next best, each with how sure. |
| 3 | **What it heard** | Twelve bars, C to B, as tall as each note has counted; the key's notes green, its root outlined. |
| 4 | **SET** | Sends the key heard to Tannin, which sets every device following it. |
| 5 | **AUTO** | Sends it every bar by itself: the house follows what you play. |
| 6 | **MEMORY** | How long a note keeps counting: its weight halves every 1, 2, 4 or 8 bars. |
| 7 | **TANNIN NOW** | The key Tannin holds now, in Tannin's blue. |
<!-- end of generated -->

## Quick start and the panel

One page with pictures first: **Dye Lot - Quick Start.pdf**, beside this manual in the download, numbers the parts to touch and gives three things to try.

1. Drag the `Dye House Utilities` folder anywhere into your User Library (for example its top level) and open it in Live's browser: Dye Lot is in its own folder there.
2. Drop it on a MIDI track you play (it passes MIDI through untouched), start Live and play.
3. After a bar or two the key appears. Press **SET** to send it to Tannin.

| Control | What it does |
| --- | --- |
| The key | The best-fitting major or minor key, checked every bar, with how sure it is; *listening* until enough has been played |
| RUNNERS-UP | The two keys that fit next best, each with how sure. How sure: how much of what you played the key explains, 100 % when every note you played is in its scale and its root is the note you played most |
| What it heard | Twelve bars, C to B, as tall as each note has counted (the most-played full). The key's notes turn green, its root outlined; grey while it's still listening |
| SET | Sends the key to Tannin, which changes the key of every device following it |
| AUTO | Sends it every bar by itself: the house follows whatever you play. Lit while on |
| MEMORY | How long a note keeps counting: its weight halves every 1, 2, 4 or 8 bars |
| TANNIN NOW | The key Tannin holds now, in Tannin's blue (*no Tannin* while there's none in the set), and whether AUTO sets it at every bar |

Each note counts by how hard it's played. The twelve note names are tallied; each of the 24 major and minor keys scores its seven notes once and its root twice, and the best wins; the next two are the runners-up. A minor and C major, the same seven notes, are often each other's runner-up: the one whose root you lean on wins.

## Use cases

### 1. Jamming into a key



Improvise on Push for a few bars, press SET, and every Mordant, Logwood and Selvedge on Key: Tannin is in that key.

### 2. Following a singer's keyboard part


Put Dye Lot on the chords track with AUTO on and a Memory of 4 bars: the house follows the harmony as it moves.

### 3. Checking a sample's key

Play along with a sample until the key settles, then read it off.

## Push 3, automation and reference

Set, Auto and Memory are on Push's **Dye Lot** page.

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| Stuck on *listening* | Play a few more notes: a single quiet note isn't enough |
| It picks the relative major or minor | Lean on the root more, or set Tannin by hand |
| It moves too often with AUTO | Use a longer Memory |

Dye Lot suggests 12-note major and minor keys only; microtonal scales are set on Tannin itself.

### Specifications

| | |
| --- | --- |
| Device type | Max for Live MIDI effect |
| Parameters | 3, all automatable, 1 Push page |
| Keys | 24: major and natural minor in all 12 roots |
| Analysis | Every bar, at Live's tempo |
| Push 3 standalone | Not yet tested; made to run there: no external files; the key screen and the bars are drawing scripts packed inside the device, which Push 3 doesn't show |

### Credits and licence

Dye Lot is designed and published by @nichbuick, as part of the Tincture family. Questions, bug reports and ideas: an issue on this repository, or a message through [Gumroad](https://nichbuick.gumroad.com).

Ableton, Live, Push and Max for Live are trademarks of Ableton AG. Max is a trademark of Cycling '74. Dye Lot is an independent product and is not affiliated with or endorsed by these companies.

## What's new

### 1.0.1 (Oct 26, 2026)

Fixed: every part of the panel now shows a line in Live's Info View when you hover it, the drawings and labels too (they showed only the object's kind). It comes with a one-page Quick Start with pictures. Your saved sets open and sound as before.

### 1.0 (Oct 23, 2026)

The first release.
