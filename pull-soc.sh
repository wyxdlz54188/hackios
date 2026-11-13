#!/bin/bash
# Pull the phone's own device tree over adb and turn it into the SoC boot-args HakiOS needs on this
# device (tools/soc-args-kona.py). The OnePlus 8T's tree describes the modem's blocks in the vendor
# kernel's own way, which is why this device uses the kona-aware reader and the common tools/soc-args.py
# (which knows the reference phone's node names) would leave soc_cmd_db and modem_ipa_fw_at out.
#
# Needs the phone in Android with adb. On this unit /sys/firmware/fdt is readable by root only, so the
# tree is copied under su to a staging file the shell can read, pulled from there, and the staging file
# is removed again. Nothing on the phone is changed.
set -e -o pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
if ! adb pull /sys/firmware/fdt "$tmp/fdt" >/dev/null 2>&1; then
	stage=/data/local/tmp/hakios-fdt
	adb shell "su -c 'cat /sys/firmware/fdt > $stage && chmod 644 $stage'" >/dev/null 2>&1 || true
	got=0; adb pull "$stage" "$tmp/fdt" >/dev/null 2>&1 || got=1
	adb shell "su -c 'rm -f $stage'" >/dev/null 2>&1 || true
	[ "$got" -eq 0 ] || { echo "pull-soc.sh: cannot read /sys/firmware/fdt over adb, with or without su"; exit 1; }
fi
# made aside and copied over, so that a failure leaves the soc.args that was there
python3 "$here/tools/soc-args-kona.py" "$tmp/fdt" > "$tmp/soc.args"
cp "$tmp/soc.args" "$here/soc.args"
cat "$here/soc.args"
echo "pull-soc.sh: wrote $here/soc.args"
