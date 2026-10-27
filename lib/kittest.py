"""Test helpers for the devices on the family bus (lib/kit.py)."""


class Tap:
    """Listens on a bus name, as a receive would: every message lands in .got."""
    def __init__(self, bus, name):
        self.got = []
        bus.receivers.setdefault(name, []).append(self)

    def out(self, outlet, msg):
        self.got.append(msg)


def say(bus, name, msg):
    """Send msg on the bus, as a send would from another device."""
    bus.deliver(name, msg)


def midi_messages(sim, start=0):
    """The MIDI a device sent since byte `start`: (kind, channel, data...), kind note/off/bend/press/cc."""
    b = sim.midi_bytes
    out, k = [], start
    while k < len(b):
        st = b[k]
        kind, ch = st & 0xF0, (st & 0x0F) + 1
        size = 2 if kind in (0xC0, 0xD0) else 3
        data = b[k + 1:k + size]
        assert st >= 0x80 and len(data) == size - 1 and all(x < 0x80 for x in data), b[k:k + size]
        if kind == 0x90 and data[1] > 0:
            out.append(("note", ch, data[0], data[1]))
        elif kind in (0x80, 0x90):
            out.append(("off", ch, data[0]))
        elif kind == 0xE0:
            out.append(("bend", ch, data[0] + 128 * data[1]))
        elif kind == 0xD0:
            out.append(("press", ch, data[0]))
        elif kind == 0xB0:
            out.append(("cc", ch, data[0], data[1]))
        k += size
    return out


class Expect:
    def __init__(self):
        self.failures = []

    def __call__(self, cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            self.failures.append(msg)

    def done(self):
        import sys
        print(f"\n{len(self.failures)} failure(s)")
        sys.exit(1 if self.failures else 0)


OWN, LIVE, TANNIN = 0, 1, 2      # the Key choice (lib/kit.py's KEY_SOURCES)


def check_follow(patch, expect, engine=None, root="Root", scale="Scale", idle="", make=None, key="Key"):
    """The Key choice (lib/kit.py's follow) in any device: Own, Live or Tannin. The device plays
    the chosen key and never changes its own Root and Scale (they grey out unless Own is chosen).
    Live: the scale of the clip playing on its track if that clip's Scale Mode is on, else Live's
    current scale if its Scale Mode is on, else its own key ('no Live scale'). Tannin: Tannin's key,
    else its own ('no Tannin'). The readout reads the key, coloured by source. root None: a device
    with no Root. engine(sim) -> (root, scale) as the device's engine got them (gen~ Params, say);
    the key leaving the choice is always checked. make(patch, bus=...): how to run the device (MaxSim's own by default;
    a probe whose panel is a bpatcher reaches its boxes by their own ids). key: the choice's name (a probe's
    Sparks Key). Returns a loaded sim on Tannin's D Dorian."""
    from kit import AMBER, BLUE, KEY, KIND_COLOR, LIVE_C, ROOTS, SCALES
    from maxsim import Bus, MaxSim

    def col(c):
        return tuple(round(v, 3) for v in c)

    def new(bus, src=OWN, **live):
        sim = (make or MaxSim)(patch, bus=bus)
        for k, v in live.items():
            setattr(sim.live, k, v)
        sim.by_name[key].value = src
        sim.load()
        return sim

    def played(sim):
        eff = (sim.objs["fk-root-eff"].sent.get(0) if root else None, sim.objs["fk-scale-eff"].sent.get(0))
        return (eff, engine(sim)) if engine else (eff, eff)

    def want(r, s_):
        return (((r if root else None), s_),) * 2

    def own(sim):
        return (sim.param(root) if root else None, sim.param(scale))

    def owns(sim):
        o = own(sim)
        return (o, o)

    def reads(sim):
        c = getattr(sim.objs["fk-readout"], "attrs", {}).get("textcolor")
        return sim.comment_text("fk-readout"), (tuple(round(float(v), 3) for v in c.split()) if c else None)

    def label(r, s_):
        return f"{ROOTS[r]} {SCALES[s_][0]}" if root else SCALES[s_][0]

    def greyed(sim):
        return [sim.by_name[m].attrs.get("active") for m in ([root] if root else []) + [scale]]

    print("Key: Tannin plays Tannin's key, and leaves the device's own alone")
    bus = Bus()
    sim = new(bus)
    mine = own(sim)
    expect(played(sim) == owns(sim), f"Own: plays its own key {played(sim)}")
    say(bus, KEY, [7, 10])
    expect(played(sim) == owns(sim), f"Own: Tannin's key is ignored {played(sim)}")
    sim.set_param(key, TANNIN)
    expect(played(sim) == owns(sim) and reads(sim)[0] == "no Tannin", f"Tannin, none stored yet: own key, {reads(sim)}")
    bus.values[KEY] = [7, 10]
    say(bus, KEY, [7, 10])
    expect(played(sim) == want(7, 10), f"Tannin's key arrives: G 19-EDO {played(sim)}")
    expect(own(sim) == mine, f"its own Root and Scale are unchanged {own(sim)}")
    expect(all(v == "0" for v in greyed(sim)), f"its own Root and Scale grey out {greyed(sim)}")
    expect(reads(sim) == (label(7, 10), col(KIND_COLOR[1])), f"the readout {reads(sim)}")
    sim.set_param(key, OWN)
    expect(played(sim) == owns(sim) and all(v == "1" for v in greyed(sim)), f"Own again: its own key, menus back {played(sim)}")
    expect(reads(sim)[0] == idle, f"readout idle: {reads(sim)}")
    sim.set_param(key, TANNIN)
    expect(played(sim) == want(7, 10), f"Tannin again: the stored key at once {played(sim)}")
    sim.live_set(scale_mode=1, root_note=5, scale_intervals=[0, 2, 4, 6, 7, 9, 11])
    expect(played(sim) == want(7, 10), f"Tannin chosen: Live's scale is ignored {played(sim)}")
    sim.live_set(scale_mode=0)
    bus.values[KEY] = "gone"
    say(bus, KEY, "gone")
    expect(played(sim) == owns(sim) and reads(sim)[0] == "no Tannin", f"Tannin leaves: own key, {reads(sim)}")
    bus = Bus()
    bus.values[KEY] = [2, 3]
    sim = new(bus, src=TANNIN)
    expect(played(sim) == want(2, 3), f"a set reopening on Tannin: D Dorian {played(sim)}")
    follower = sim

    print("Key: Live plays Live's scale, as Live's own devices take it")
    sim = new(Bus(), src=LIVE, root_note=5, scale_intervals=[0, 2, 4, 6, 7, 9, 11])
    expect(played(sim) == owns(sim) and reads(sim)[0] == "no Live scale", f"Scale Mode off: own key, {reads(sim)}")
    sim.live_set(scale_mode=1)
    expect(played(sim) == want(5, 12) and reads(sim) == (label(5, 12), col(LIVE_C)),
           f"Scale Mode on: F Lydian, purple {played(sim)} {reads(sim)}")
    expect(own(sim) != (5, 12) or not root, f"its own Root and Scale are unchanged {own(sim)}")
    sim.bus.values[KEY] = [0, 1]
    say(sim.bus, KEY, [0, 1])
    expect(played(sim) == want(5, 12), f"Live chosen: Tannin's key is ignored {played(sim)}")
    sim.live_set(root_note=11, scale_intervals=[0, 1, 3, 5, 6, 8, 10])
    expect(played(sim) == want(11, 13), f"follows Live's changes: B Locrian {played(sim)}")
    sim.live_set(scale_intervals=[0, 2, 3, 6, 7, 8, 11])
    expect(played(sim) == want(11, 0) and reads(sim)[1] == col(AMBER),
           f"a Live scale the family lacks (Hungarian Minor): Chromatic, amber {played(sim)} {reads(sim)}")
    clip = {"length": 4.0, "notes": [], "scale_mode": 1, "root_note": 2, "scale_intervals": [0, 2, 3, 5, 7, 9, 10]}
    sim.live.slots[1] = clip
    sim.live_set(playing_slot_index=1)
    expect(played(sim) == want(2, 3), f"the clip playing on its track first: D Dorian {played(sim)}")
    sim.set_clip(1, root_note=4)
    expect(played(sim) == want(4, 3), f"the clip's scale changes: E Dorian {played(sim)}")
    sim.set_clip(1, scale_mode=0)
    expect(played(sim) == want(11, 0), f"the clip's Scale Mode off: Live's current scale {played(sim)}")
    sim.set_clip(1, scale_mode=1)
    sim.live_set(playing_slot_index=-1)
    expect(played(sim) == want(11, 0), f"the clip stops: Live's current scale {played(sim)}")
    sim.live_set(scale_mode=0)
    expect(played(sim) == owns(sim) and reads(sim)[0] == "no Live scale", f"Scale Mode off: own key {played(sim)}")
    sim.live_set(scale_mode=1, scale_intervals=[0, 2, 3, 5, 7, 8, 10])
    sim.set_param(key, OWN)
    expect(played(sim) == owns(sim), f"Own: Live's scale is ignored {played(sim)}")
    sim.set_param(key, LIVE)
    expect(played(sim) == want(11, 2), f"Live again: B Minor at once {played(sim)}")
    sim = new(Bus(), src=LIVE, scale_mode=1, root_note=10, scale_intervals=[0, 2, 4, 5, 7, 9, 10])
    expect(played(sim) == want(10, 11), f"a set reopening on Live: Bb Mixolydian {played(sim)}")
    expect(not sim.live.calls, f"never writes to Live: {sim.live.calls}")

    print("Key: Live or Tannin with no key there plays its own Root and Scale, in any reopening order")
    for src in (LIVE, TANNIN):
        wrong = []
        for seed in range(8):
            sim = MaxSim(patch, bus=Bus(), seed=seed)
            sim.by_name[key].value = src
            if root:
                sim.by_name[root].value = 10
            sim.by_name[scale].value = 3
            sim.load("shuffle")
            if played(sim) != want(10, 3):
                wrong.append((seed, played(sim)))
        expect(not wrong, f"{'Live' if src == LIVE else 'Tannin'} chosen, none there, saved "
                          f"{label(10, 3)}: played in every order {wrong or ''}")
        sim.set_param(scale, 4)
        if root:
            sim.set_param(root, 2)
        expect(played(sim) == want(2, 4),
               f"then its own Root and Scale are heard as they change {played(sim)}")
    return follower


def check_rinse(patch, expect, name, gen_devices=False):
    """The reset (dyehouse_rinse) reaches the device: a MIDI device sends all notes off (and bend,
    pressure and timbre reset, sustain pedal up) on all 16 channels for 'rinse' and 'wipe'; an MPE synth
    (gen_devices) gets a new 'rinse' count in gen~ each time."""
    from kit import RINSE, reset_bytes
    from maxsim import Bus, MaxSim
    print(f"{name} answers the reset")
    bus = Bus()
    sim = MaxSim(patch, bus=bus)
    sim.load()
    if gen_devices:
        def count():
            got = [m[1] for m in getattr(sim.objs["gen"], "received", []) if isinstance(m, list) and m[0] == "rinse"]
            return got[-1] if got else None
        say(bus, RINSE, "rinse")
        a = count()
        say(bus, RINSE, "wipe")
        b = count()
        expect(a is not None and b is not None and b != a, f"'rinse' and 'wipe' each let every voice go (count {a}, {b})")
        return sim
    for word in ("rinse", "wipe"):
        n = len(sim.midi_bytes)
        say(bus, RINSE, word)
        expect(sim.midi_bytes[n:] == reset_bytes(), f"'{word}': all notes off on all 16 channels "
                                                    f"({len(sim.midi_bytes) - n} bytes)")
    return sim
