#!/usr/bin/env python3
"""Pack the kebab UEFI, its BootShim and a payload into an Android boot image for `fastboot boot`.

This is the common tree's mkxnuimg.py for the OnePlus 8T: same layout (gzip(BootShim + UEFI FD +
"XNUP" payload) + DTB), but the numbers are this phone's, out of Mu-Silicium's
Resources/Configs/kebab.toml and its kebabPkg:

  UEFI FD   0x9FC00000, 0x300000   (kebab.toml; mkxnuimg.py's 0x9FD00000 is redwood's)
  payload   0xF0000000, 0x04000000 (the BootShim copies the "XNUP" container there)
  DTB       this phone's own prebuilt/device-tree.dtb

The payload's loader entry MUST be named "loader.efi": HakiOS's XnuLoaderMain looks for exactly that
name (StartPayloadLoader, XnuLoader.c). Built as anything else, the UEFI silently skips the real
loader, falls into its stage-0 diagnostics and -- on this phone -- dies reading the unmapped payload
window, which is what took the first attempts to Qualcomm's 900E diagnostics mode. So this script
builds the payload itself from --loader, and refuses a --payload whose first entry is not loader.efi.

usage:
  mkimg.py --loader <loader.efi>              build the USB-resident payload and the image
  mkimg.py --payload <payload.bin> -o out.img use an existing XNUP payload (checked)
"""
import argparse
import gzip
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))   # devices/<name>/uefi -> the common tree
FD_BASE, FD_SIZE = 0x9FC00000, 0x300000
PAYLOAD_BASE, PAYLOAD_MAX = 0xF0000000, 0x04000000

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--payload', help='an existing XNUP payload (whose entry must be loader.efi)')
ap.add_argument('-l', '--loader', help='a loader.efi to put into a USB-resident payload')
ap.add_argument('-o', '--output', default=os.path.join(REPO, 'xnu-oneplus8t.img'))
ap.add_argument('--mode', default='RELEASE')
ap.add_argument('--mu', default=os.path.join(REPO, 'Mu-Silicium'))
ap.add_argument('--dtb', default=os.path.join(REPO, 'devices', 'oneplus8t', 'prebuilt', 'device-tree.dtb'))
args = ap.parse_args()
if not args.payload and not args.loader:
    sys.exit('mkimg: give --loader FILE (build the payload) or --payload FILE (use one made elsewhere)')


def xnup(entries):
    """The "XNUP" container: magic, size after the header, then name[16] size reserved data, and an
    empty name to end it (xnuloader/mkpayload.py)."""
    body = b''
    for name, data in entries:
        body += struct.pack('<16sII', name.encode(), len(data), 0)
        body += data + b'\0' * (-len(data) % 16)
    body += struct.pack('<16sII', b'', 0, 0)
    return b'XNUP' + struct.pack('<I', len(body)) + body


def payload_entries(data):
    if data[:4] != b'XNUP':
        sys.exit('mkimg: the payload does not start with XNUP')
    size, = struct.unpack('<I', data[4:8])
    at, end, out = 8, 8 + size, []
    while at + 24 <= end:
        name, n, _res = struct.unpack('<16sII', data[at:at + 24])
        name = name.split(b'\0')[0].decode(errors='replace')
        if not name:
            break
        out.append((name, n))
        at += 24 + ((n + 15) // 16) * 16
    return out


if args.loader:
    if not os.path.isfile(args.loader):
        sys.exit(f'mkimg: no {args.loader}')
    payload = xnup([('loader.efi', open(args.loader, 'rb').read())])
    payload_path = os.path.join('/tmp', 'usb-payload.bin') if os.path.isdir('/tmp') else args.output + '.payload'
    open(payload_path, 'wb').write(payload)
    print(f'mkimg: payload {len(payload)} bytes (loader.efi <- {args.loader})')
    args.payload = payload_path

data = open(args.payload, 'rb').read()
entries = payload_entries(data)
print('mkimg: payload entries:', ', '.join(f'{n} ({s} bytes)' for n, s in entries) or '(none)')
if not entries or entries[0][0] != 'loader.efi':
    sys.exit('mkimg: the payload\'s first entry is not loader.efi: the UEFI would not start the loader '
             '(see the top of this file)')
if len(data) > PAYLOAD_MAX - 0x1000:
    sys.exit('mkimg: payload too big')

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

blob = shim + fd + data
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
      f'payload {len(data)}, dtb {len(dtb)}, uncompressed {len(blob)})')
