#!/usr/bin/env python3
"""Check that this device repository holds together, without the common HakiOS tree.

usage: python3 tools/check-port.py [DIR]     (DIR defaults to this repository)

What it checks, and why each is a real failure:

  device.conf     the one block `device NAME`, the words tools/hakios-device.py reads
                  (title/vendor/soc/defconfig/firmware/maintainer), and status lines whose area and
                  value are from the allowed sets -- a typo there is a status that never shows up.
  configs/        <name>_defconfig's #include lines resolve to this repository's own files, and
                  <name>.config sets CONFIG_DEVICE to the same name.
  soc/            soc.conf names the same SoC the device block does, and soc/configs/<soc>.config exists.
  soc.args        every line is key=value with a known soc_*/modem_* key and a number that fits 64 bits.
  prebuilt/       the device tree is a flattened device tree (magic d00dfeed).
  ios17/          the patch is there, and it is the 10002 one.
"""
import os
import re
import struct
import sys

AREAS = ("display", "touch", "buttons", "cpu", "gpu", "storage", "audio", "battery", "haptic",
         "camera", "torch", "wifi", "bluetooth", "cellular", "network", "thermal", "usb", "sensors")
VALUES = ("works", "partial", "missing")
STATUS_KEYS = ("title", "vendor", "soc", "defconfig", "firmware", "maintainer")
SOC_ARGS = ("soc_ipa_base", "soc_gsi_base", "soc_ipcc", "soc_aoss", "soc_rsc", "soc_apps_smmu",
            "soc_cmd_db", "soc_mpss_mem", "modem_ipa_fw_at", "soc_smem", "soc_imem",
            "soc_ipa_stream", "soc_ipa_stream_uc", "soc_pas_mpss", "soc_pas_ipa", "soc_ipa_fw")
# fragments that live in the common tree, not in a device repository
COMMON_FRAGMENTS = ("common_defconfig", "open.config", "virt.config", "defconfig")

problems, notes = [], []


def bad(msg):
    problems.append(msg)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    conf_path = os.path.join(root, "device.conf")
    if not os.path.isfile(conf_path):
        sys.exit("check-port: no device.conf in %s" % root)
    text = open(conf_path, encoding="utf-8").read()
    device = None
    fields = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("device "):
            if device is not None:
                bad("device.conf: more than one `device` line")
            device = line.split()[1]
            continue
        m = re.match(r"\t(\w+)\s+(.*)$", line)
        if not m:
            bad("device.conf: cannot read line %r (tab-indented KEY VALUE expected)" % line)
            continue
        key, rest = m.group(1), m.group(2).strip()
        if key == "status":
            parts = rest.split(None, 2)
            if len(parts) < 2:
                bad("device.conf: status line %r needs AREA VALUE [note]" % line)
                continue
            area, value = parts[0], parts[1]
            note = parts[2] if len(parts) > 2 else ""
            if area not in AREAS:
                bad("device.conf: status area %r is not one of %s" % (area, ", ".join(AREAS)))
            elif value not in VALUES:
                bad("device.conf: status of %s is %r, not works|partial|missing" % (area, value))
            elif value != "works" and not note:
                notes.append("status %s: %s without a note (docs/porting/index.md asks for the how)" % (area, value))
        elif key in STATUS_KEYS:
            fields[key] = rest
        else:
            bad("device.conf: unknown word %r" % key)
    if not device:
        bad("device.conf: no `device NAME` line")
    for k in ("title", "vendor", "soc", "defconfig", "firmware"):
        if k not in fields:
            bad("device.conf: no %s" % k)

    # configs
    name = device or "?"
    defconfig = os.path.join(root, "configs", fields.get("defconfig", name + "_defconfig"))
    if os.path.isfile(defconfig):
        for line in open(defconfig, encoding="utf-8"):
            m = re.match(r"#include\s+(\S+)", line.strip())
            if not m:
                continue
            inc = m.group(1)
            here = [os.path.join(root, "configs", inc), os.path.join(root, "soc", "configs", inc)]
            if any(os.path.isfile(p) for p in here):
                continue
            if inc in COMMON_FRAGMENTS:
                notes.append("configs/%s: #include %s comes from the common tree (correct there)"
                             % (os.path.basename(defconfig), inc))
            else:
                bad("configs/%s: #include %s is in neither this repository (configs/, soc/configs/) nor the "
                    "common tree" % (os.path.basename(defconfig), inc))
    else:
        bad("configs/: no %s" % os.path.basename(defconfig))
    devconf = os.path.join(root, "configs", name + ".config")
    if os.path.isfile(devconf):
        body = open(devconf, encoding="utf-8").read()
        m = re.search(r'^CONFIG_DEVICE="(\w+)"', body, re.M)
        if not m or m.group(1) != name:
            bad("configs/%s.config: CONFIG_DEVICE is not \"%s\"" % (name, name))
    else:
        bad("configs/: no %s.config" % name)

    # soc/
    socconf = os.path.join(root, "soc", "soc.conf")
    soc = fields.get("soc")
    if os.path.isfile(socconf):
        body = open(socconf, encoding="utf-8").read()
        m = re.search(r"^soc\s+(\S+)", body, re.M)
        if not m:
            bad("soc/soc.conf: no `soc NAME` line")
        elif soc and m.group(1) != soc:
            bad("soc/soc.conf names %r, device.conf says soc %r" % (m.group(1), soc))
        frag = os.path.join(root, "soc", "configs", (soc or "?") + ".config")
        if not os.path.isfile(frag):
            bad("soc/configs/: no %s.config" % soc)
    elif soc and soc != "none":
        bad("soc/: no soc.conf though device.conf says soc %s" % soc)

    # soc.args
    path = os.path.join(root, "soc.args")
    if os.path.isfile(path):
        seen = {}
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                bad("soc.args: %r is not key=value" % line)
                continue
            k, v = line.split("=", 1)
            if k not in SOC_ARGS:
                bad("soc.args: unknown argument %r" % k)
                continue
            if k == "soc_ipa_fw":
                continue
            try:
                n = int(v, 16)
            except ValueError:
                bad("soc.args: %s=%r is not a hex number" % (k, v))
                continue
            if not 0 <= n < 1 << 64:
                bad("soc.args: %s does not fit 64 bits" % k)
            seen[k] = n
        for k in ("soc_ipa_base", "soc_gsi_base", "soc_smem", "soc_imem"):
            if k not in seen:
                notes.append("soc.args has no %s" % k)
        for k in ("soc_mpss_mem", "soc_pas_mpss", "modem_ipa_fw_at"):
            if k not in seen:
                notes.append("soc.args has no %s: %s" % (k, {
                    "soc_mpss_mem": "this phone's tree has no modem reservation node",
                    "soc_pas_mpss": "this phone's tree has no qcom,mss node",
                    "modem_ipa_fw_at": "this phone's tree has no ipa_gsi reservation",
                }.get(k, "missing from the tree")))
    else:
        bad("no soc.args (run pull-soc.sh)")

    # prebuilt/device-tree.dtb
    dtb = os.path.join(root, "prebuilt", "device-tree.dtb")
    if os.path.isfile(dtb):
        with open(dtb, "rb") as f:
            magic = f.read(4)
        if magic != b"\xd0\x0d\xfe\xed":
            bad("prebuilt/device-tree.dtb is not a flattened device tree")
        else:
            size, = struct.unpack(">I", open(dtb, "rb").read(8)[4:8])
            notes.append("prebuilt/device-tree.dtb: %d bytes, totalsize %d" % (os.path.getsize(dtb), size))
    else:
        bad("prebuilt/device-tree.dtb is missing (adb pull /sys/firmware/fdt)")

    # soc/thermal/kona-thermal-table.h: is it still what the tool makes from this tree?
    table = os.path.join(root, "soc", "thermal", "kona-thermal-table.h")
    if os.path.isfile(table) and os.path.isfile(dtb):
        import subprocess
        tool = os.path.join(root, "tools", "dt-thermal.py")
        run = subprocess.run([sys.executable, tool, dtb, "--c"], capture_output=True, text=True)
        if run.returncode:
            bad("tools/dt-thermal.py failed: " + (run.stderr or "").strip()[:200])
        else:
            row = re.compile(r'\{\s*"([^"]+)",\s*(0x[0-9a-fA-F]+),\s*(\d+),\s*(-?\d+),\s*(-?\d+)\s*\}')
            want = row.findall(run.stdout)
            have = row.findall(open(table, encoding="utf-8").read())
            if not have:
                bad("soc/thermal/kona-thermal-table.h: no rows read")
            elif want != have:
                only_want = [r for r in want if r not in have]
                only_have = [r for r in have if r not in want]
                bad("soc/thermal/kona-thermal-table.h differs from what this tree gives: %d row(s) missing, "
                    "%d row(s) extra (first missing: %s)" % (len(only_want), len(only_have),
                                                             only_want[0][0] if only_want else "-"))
            else:
                notes.append("soc/thermal/kona-thermal-table.h: %d sensors, same as tools/dt-thermal.py makes" % len(have))

    # ios17/
    patch = os.path.join(root, "ios17", "hakios-xnu-10002.1.13.patch")
    if os.path.isfile(patch):
        head = open(patch, encoding="utf-8", errors="replace").read(400000).replace("\r\n", "\n")
        n = head.count("\ndiff --git ") + (1 if head.startswith("diff --git ") else 0)
        if "xnu/hakios.patch" in head and n < 10:
            bad("ios17 patch: looks like the 16.5 patch, not a rebase")
        notes.append("ios17 patch: %d file sections in its first 400 kB, %.1f MB on disk"
                     % (n, os.path.getsize(patch) / 1e6))
    else:
        bad("ios17/hakios-xnu-10002.1.13.patch is missing")

    print("check-port: %s (%s, %s, soc %s)" % (name, fields.get("title", "?"), fields.get("vendor", "?"), soc))
    for n in notes:
        print("  note: " + n)
    if problems:
        for p in problems:
            print("  FAIL: " + p)
        print("check-port: %d problem(s)" % len(problems))
        return 1
    print("check-port: ok -- device.conf, configs, soc layer, soc.args, the device tree and the iOS 17 patch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
