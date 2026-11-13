#!/usr/bin/env python3
"""Pack the kebab UEFI, its BootShim and a payload into an Android boot image for `fastboot boot`.

This is the common tree's mkxnuimg.py for the OnePlus 8T: same layout (gzip(BootShim + UEFI FD +
"XNUP" payload) + DTB), but the numbers are this phone's, out of Mu-Silicium's
Resources/Configs/kebab.toml and its kebabPkg:

  UEFI FD   0x9FC00000, 0x300000   (kebab.toml; mkxnuimg.py's 0x9FD00000 is redwood's)
  payload   0xF0000000, 0x04000000 (the BootShim copies the "XNUP" container there)
  DTB       this phone's own prebuilt/device-tree.dtb

usage: mkimg.py [-p payload.bin] [-o out.img] [--mu DIR] [--dtb FILE] [--mode RELEASE]
"""
import argparse
import gzip
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))   # devices/<name>/uefi -> the common tree
FD_BASE, FD_SIZE = 0x9FC00000, 0x300000
PAYLOAD_BASE, PAYLOAD_MAX = 0xF0000000, 0x04000000

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--payload')
ap.add_argument('-o', '--output', default=os.path.join(REPO, 'xnu-oneplus8t.img'))
ap.add_argument('--mode', default='RELEASE')
ap.add_argument('--mu', default=os.path.join(REPO, 'Mu-Silicium'))
ap.add_argument('--dtb', default=os.path.join(REPO, 'devices', 'oneplus8t', 'prebuilt', 'device-tree.dtb'))
args = ap.parse_args()

fd_path = os.path.join(args.mu, f'Build/kebabPkg/{args.mode}_CLANGPDB/FV/SILICIUM_UEFI.fd')
if not os.path.isfile(fd_path):
    sys.exit(f'mkimg: no {fd_path}: build Mu-Silicium for kebab first (uefi/README.md)')
shim_dir = os.path.join(args.mu, 'BootShim')
for f in ('BootShim.elf', 'BootShim.bin'):
    try:
        os.unlink(os.path.join(shim_dir, f))
    except FileNotFoundError:
        pass
subprocess.check_call(['make', 'REQUIRES_KERNEL_HEADER=1', f'FD_BASE={FD_BASE:#x}', f'FD_SIZE={FD_SIZE:#x}',
                       f'CFLAGS=--target=aarch64-linux-gnu -DPAYLOAD_BASE={PAYLOAD_BASE:#x}'],
                      cwd=shim_dir, stdout=subprocess.DEVNULL)
parts = {
    'shim': os.path.join(shim_dir, 'BootShim.bin'),
    'fd': fd_path,
    'dtb': args.dtb,
    'ramdisk': os.path.join(args.mu, 'Resources/ramdisk'),
    'mkbootimg': os.path.join(args.mu, 'Resources/Scripts/mkbootimg.py'),
}
for name, path in parts.items():
    if not os.path.isfile(path):
        sys.exit(f'mkimg: {path} not found')

shim = open(parts['shim'], 'rb').read()
fd = open(parts['fd'], 'rb').read()
if len(fd) != FD_SIZE:
    sys.exit(f'mkimg: the FD is {len(fd):#x} bytes, kebab.toml says {FD_SIZE:#x}')

blob = shim + fd
if args.payload:
    data = open(args.payload, 'rb').read()
    if data[:4] != b'XNUP' or len(data) > PAYLOAD_MAX - 0x1000:
        sys.exit('mkimg: bad or oversized payload')
    blob += data
    blob += b'\0' * (-len(blob) % 16)

dtb = open(parts['dtb'], 'rb').read()
kernel = args.output + '.kernel~'
open(kernel, 'wb').write(gzip.compress(blob, 6) + dtb)
try:
    subprocess.check_call([sys.executable, parts['mkbootimg'], '--kernel', kernel, '--ramdisk', parts['ramdisk'],
                           '--header_version', '1', '-o', args.output])
finally:
    os.unlink(kernel)
print(f'mkimg: {args.output}: {os.path.getsize(args.output)} bytes (shim {len(shim)}, FD {len(fd)}, '
      f'dtb {len(dtb)}, uncompressed {len(blob)})')
