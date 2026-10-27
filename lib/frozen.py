"""Frozen Max for Live devices: the device's patcher and the files it needs (JavaScript
drawing scripts, above all), in one .amxd, as Max's Freeze Device writes it.

Read from devices Max froze (tests/test_frozen.py rebuilds them byte for byte):

    ampf <u32 LE 4> <kind: aaaa / mmmm / iiii>
    meta <u32 LE 4> <u32 LE flags>                 7 in the frozen devices seen
    ptch <u32 LE size> then, big-endian from here:
        mx@c <u32 16> <u32 0> <u32 offset of dlst>  (offsets count from the 'mx@c')
        the files' bytes, one after another, the device's own patcher first
        dlst <u32 size> and a 'dire' per file, each a list of fields
            <tag> <u32 size, the 8 header bytes included> <data>:
            type (JSON for a patcher, TEXT for a script...), fnam (the name, NUL-padded to a
            multiple of 4, at least one NUL), sz32, of32, vers, flag (17 for the device's own
            patcher, 0 for the others), mdat (a Mac time: seconds since 1904)

The device's own patcher is the JSON text with a NUL at its end, as in an unfrozen device.
"""

import struct
import time

MAC_EPOCH = 2082844800          # seconds from 1904-01-01 to 1970-01-01
MAIN_FLAG = 17


class File:
    def __init__(self, name, data, type_=None, flag=0, vers=0, mdat=None):
        self.name, self.data, self.flag, self.vers = name, data, flag, vers
        self.type = type_ or ("JSON" if name.endswith((".maxpat", ".amxd", ".json")) else "TEXT")
        self.mdat = mdat if mdat is not None else int(time.time()) + MAC_EPOCH

    def __repr__(self):
        return f"File({self.name!r}, {len(self.data)} bytes, {self.type}, flag {self.flag})"


def _field(tag, payload):
    return tag + struct.pack(">I", 8 + len(payload)) + payload


def _name(name):
    raw = name.encode("utf-8")
    return raw + b"\x00" * (4 - len(raw) % 4)          # one NUL at least, up to a multiple of 4


def pack(kind, files, meta=7):
    """The .amxd bytes: files[0] is the device's own patcher (flag 17)."""
    body, offsets = b"", []
    for f in files:
        offsets.append(16 + len(body))
        body += f.data
    dirs = b""
    for f, off in zip(files, offsets):
        fields = (_field(b"type", f.type.encode("ascii")) + _field(b"fnam", _name(f.name))
                  + _field(b"sz32", struct.pack(">I", len(f.data))) + _field(b"of32", struct.pack(">I", off))
                  + _field(b"vers", struct.pack(">I", f.vers)) + _field(b"flag", struct.pack(">I", f.flag))
                  + _field(b"mdat", struct.pack(">I", f.mdat & 0xFFFFFFFF)))
        dirs += _field(b"dire", fields)
    dlst = _field(b"dlst", dirs)
    ptch = b"mx@c" + struct.pack(">III", 16, 0, 16 + len(body)) + body + dlst
    return (b"ampf" + struct.pack("<I", 4) + kind + b"meta" + struct.pack("<II", 4, meta)
            + b"ptch" + struct.pack("<I", len(ptch)) + ptch)


def _fields(data):
    out, i = [], 0
    while i < len(data):
        tag, (size,) = data[i:i + 4], struct.unpack(">I", data[i + 4:i + 8])
        out.append((tag, data[i + 8:i + size]))
        i += size
    return out


def is_frozen(data):
    return data[:4] == b"ampf" and data[32:36] == b"mx@c"


def parse(data):
    """(kind, meta, [File]) from a frozen .amxd's bytes."""
    assert data[:4] == b"ampf" and data[12:16] == b"meta" and data[24:28] == b"ptch", "not an amxd"
    kind = data[8:12]
    (meta,) = struct.unpack("<I", data[20:24])
    (size,) = struct.unpack("<I", data[28:32])
    ptch = data[32:32 + size]
    assert ptch[:4] == b"mx@c", "not frozen"
    _, _, dlst_at = struct.unpack(">III", ptch[4:16])
    assert ptch[dlst_at:dlst_at + 4] == b"dlst"
    files = []
    for tag, dire in _fields(ptch[dlst_at + 8:]):
        assert tag == b"dire"
        f = dict(_fields(dire))
        (sz,), (off,) = struct.unpack(">I", f[b"sz32"]), struct.unpack(">I", f[b"of32"])
        files.append(File(f[b"fnam"].rstrip(b"\x00").decode("utf-8"), ptch[off:off + sz],
                          f[b"type"].decode("ascii"), struct.unpack(">I", f[b"flag"])[0],
                          struct.unpack(">I", f[b"vers"])[0], struct.unpack(">I", f[b"mdat"])[0]))
    return kind, meta, files
