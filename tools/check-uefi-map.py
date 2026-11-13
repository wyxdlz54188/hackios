#!/usr/bin/env python3
"""Compare a Mu-Silicium platform's memory map with this phone's own device tree.

usage: tools/check-uefi-map.py PLATFORM-DIR DEVICE-TREE.dtb

PLATFORM-DIR is the platform package of a Mu-Silicium checkout, e.g.
Mu-Silicium/Platforms/OnePlus/kebabPkg. The platform's MemoryMapLib.c is the map the UEFI gives
itself; the device tree's /reserved-memory is what this phone's firmware and its Android kernel keep
for themselves. They are not the same thing (Android's reservations are not live while the UEFI runs),
so the report says what each side does not know about -- and, separately, which fixed windows the UEFI
cannot move (the FD, its stack, its heap) sit on a reservation of this phone: the one class of
collision that editing the driver list does not fix.
"""
import re
import struct
import sys


def regions_of_dtb(path):
    blob = open(path, 'rb').read()
    off_struct, off_strings = struct.unpack('>II', blob[8:16])
    size_strings, = struct.unpack('>I', blob[32:36])
    strings = blob[off_strings:off_strings + size_strings]
    nodes, stack, at = {}, [], off_struct
    while True:
        token, = struct.unpack('>I', blob[at:at + 4])
        at += 4
        if token == 1:
            end = blob.index(b'\0', at)
            stack.append(blob[at:end].decode(errors="replace"))
            at = (end + 4) & ~3
            key = '/'.join(stack)
            nodes[key if key.startswith('/') else '/' + key] = {}
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, name_off = struct.unpack('>II', blob[at:at + 8])
            at += 8
            name = strings[name_off:strings.index(b'\0', name_off)].decode()
            key = '/'.join(stack)
            nodes[key if key.startswith('/') else '/' + key][name] = blob[at:at + length]
            at = (at + length + 3) & ~3
        elif token == 9:
            break
        elif token != 4:
            sys.exit('check-uefi-map: not a device tree')

    out = []
    for path, props in nodes.items():
        if not path.startswith('/reserved-memory/') or path.count('/') != 2 or 'reg' not in props:
            continue
        parent = nodes[path.rsplit('/', 1)[0]]
        ac = struct.unpack('>I', parent.get('#address-cells', struct.pack('>I', 2)))[0]
        sc = struct.unpack('>I', parent.get('#size-cells', struct.pack('>I', 1)))[0]
        data = props['reg']
        stride = 4 * (ac + sc)
        for off in range(0, len(data) - stride + 1, stride):
            address = int.from_bytes(data[off:off + 4 * ac], 'big')
            size = int.from_bytes(data[off + 4 * ac:off + 4 * (ac + sc)], 'big')
            out.append((address, size, path.split('/')[-1]))
    return out


def regions_of_map(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    out = []
    for m in re.finditer(r'\{\s*"([^"]+)",\s*(0x[0-9A-Fa-f]+|\d+),\s*(0x[0-9A-Fa-f]+|\d+)', text):
        out.append((int(m.group(2), 0), int(m.group(3), 0), m.group(1)))
    return out


def overlaps(a, b):
    return a[0] < b[0] + b[1] and b[0] < a[0] + a[1]


def main():
    platform, dtb = sys.argv[1], sys.argv[2]
    mmap = platform + '/Library/MemoryMapLib/MemoryMapLib.c'
    uefi = regions_of_map(mmap)
    dt = [(a, s, n) for a, s, n in regions_of_dtb(dtb) if s]
    if not uefi:
        sys.exit('check-uefi-map: no entries read from ' + mmap)
    print("UEFI map: %d regions; this phone's tree: %d reservations" % (len(uefi), len(dt)))

    fixed_name = re.compile(r'^(UEFI FD|SEC Heap|MMU PageTables|UEFI Stack|Log Buffer|Info Blk|FV Region|ABOOT FV|Kernel|DXE Heap|Display Reserved)$')

    print("\n== fixed UEFI windows that sit on one of this phone's reservations ==")
    hits = 0
    for a, s, n in sorted(uefi):
        if not fixed_name.match(n):
            continue
        for da, ds, dn in dt:
            if overlaps((a, s), (da, ds)):
                hits += 1
                print("  UEFI %-14s %#012x +%6.1f MB  on  %-34s %#012x +%6.1f MB"
                      % (n, a, s / 1048576, dn, da, ds / 1048576))
    if not hits:
        print("  (none)")

    print("\n== this phone's reservations the UEFI map does not cover ==")
    missing = [r for r in sorted(dt) if not any(overlaps(r, u) for u in uefi)]
    for a, s, n in missing:
        print("  %#012x +%8.1f MB  %s" % (a, s / 1048576, n))
    if not missing:
        print("  (none)")
    print("\n%d of %d reservations are not in the UEFI map. Expected for Android-only carveouts"
          " (splash, dfps, ramoops), worth checking for anything a firmware block owns (PIL, ADSP,"
          " modem)." % (len(missing), len(dt)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
