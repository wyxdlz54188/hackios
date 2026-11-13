#!/bin/bash
# Print, read only, everything this port reads from the phone: identity, boot state as the bootloader
# says it, partitions, input devices, GPU, and the key nodes of its device tree. Nothing is written;
# the only file it makes is prebuilt/device-tree.dtb when --dtb is given.
#
# usage: tools/collect-device.sh [--dtb]
#
# Runs on Windows (Git Bash) and Linux. Root is used when `su -c true` answers; without it some of the
# output is missing, which the script says instead of pretending.
set -u
cd "$(dirname "$0")/.."
SU=""
if adb shell 'su -c true' >/dev/null 2>&1; then SU="su -c "; echo "collect-device: root through su"; else echo "collect-device: no root; some lines will be missing"; fi
run() { adb shell "$SU$1" 2>&1 | tr -d '\r'; }
sec() { echo; echo "===== $1"; }

sec "adb"
adb devices -l

sec "identity"
run "getprop ro.product.model; getprop ro.product.device; getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.product.cpu.abi; getprop ro.soc.manufacturer; getprop ro.soc.model; getprop ro.build.fingerprint; getprop ro.boot.serialno"

sec "boot state (the bootloader's own words: /proc/cmdline, not getprop)"
run "cat /proc/cmdline" | tr ' ' '\n' | grep -E 'androidboot\.(vbmeta\.device_state|verifiedbootstate|flash\.locked|slot_suffix|project_codename|hw_version|dtbo_idx|baseband|boot_devices)|msm_drm\.dsi_display0|earlycon'
run "getprop ro.boot.flash.locked; getprop ro.boot.verifiedbootstate"

sec "kernel"
run "cat /proc/version"

sec "memory"
run "cat /proc/meminfo" | head -3

sec "partitions"
run "cat /proc/partitions" | head -40
run "ls -l /dev/block/by-name" | head -60

sec "input devices"
run "cat /proc/bus/input/devices" | grep -E '^(N|H|S):'

sec "gpu"
run "cat /sys/class/kgsl/kgsl-3d0/gpu_model"

sec "device tree: the nodes this port reads"
run "cat /sys/firmware/fdt" >/dev/null 2>&1 && echo "the tree is readable; use --dtb to save it" || echo "the tree is root-only (this unit is)"

if [ "${1:-}" = "--dtb" ]; then
	sec "device tree -> prebuilt/device-tree.dtb"
	mkdir -p prebuilt
	if adb pull /sys/firmware/fdt prebuilt/device-tree.dtb >/dev/null 2>&1; then
		echo "collect-device: saved prebuilt/device-tree.dtb ($(wc -c < prebuilt/device-tree.dtb) bytes)"
	else
		stage=/data/local/tmp/hakios-fdt
		adb shell "su -c 'cat /sys/firmware/fdt > $stage && chmod 644 $stage'" >/dev/null 2>&1
		adb pull "$stage" prebuilt/device-tree.dtb >/dev/null 2>&1 && echo "collect-device: saved prebuilt/device-tree.dtb through su" \
			|| echo "collect-device: could not read /sys/firmware/fdt"
		adb shell "su -c 'rm -f $stage'" >/dev/null 2>&1
	fi
	[ -f prebuilt/device-tree.dtb ] && python3 tools/soc-args-kona.py prebuilt/device-tree.dtb
fi

sec "what the kernel's own drivers say about the reference phone"
echo "(nothing here: the drivers are the common repository's, and their heads say where their numbers came from)"
