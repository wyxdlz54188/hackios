#!/bin/bash
# pull-firmware.sh, through root. On this unit (OnePlus 8T, KB2000, Android 14) /vendor/firmware_mnt
# is root-only and /vendor/firmware is not readable by the adb shell user either: the plain `adb pull`
# of pull-firmware.sh gets nothing ("not on the phone" for every file) although every file is there.
# This does the same pull by way of su: the firmware is copied, under root, to a world-readable staging
# directory in /data/local/tmp, pulled from there, and the staging directory is removed again.
# Nothing on the phone is changed. Needs the phone in Android with adb and a root that answers `su -c`.
#
# The layout it leaves is pull-firmware.sh's: fw-gpu/, fw-wifi/ (with qca_cld/), fw-audio/, fw-ipa/,
# fw-modem/ (modem.* and image/, the modem's own files for TFTP).
set -e
cd "$(dirname "$0")"
S=/data/local/tmp/fw
adb get-state >/dev/null
adb shell "su -c 'sh -c \"
S=$S; rm -rf \$S; mkdir -p \$S/gpu \$S/wifi \$S/audio \$S/ipa \$S/modem
cp /vendor/firmware/a650_gmu.bin /vendor/firmware/a650_sqe.fw /vendor/firmware/a650_zap.* \$S/gpu/ 2>/dev/null
cp /vendor/firmware_mnt/image/wpss.* \$S/wifi/ 2>/dev/null
cp -r /vendor/firmware/wlan/qca_cld \$S/wifi/ 2>/dev/null
cp /vendor/firmware_mnt/image/adsp.* \$S/audio/ 2>/dev/null
cp /vendor/firmware/ipa_fws.* \$S/ipa/ 2>/dev/null
cp /vendor/firmware_mnt/image/modem.* \$S/modem/ 2>/dev/null
cp -r /vendor/firmware_mnt/image \$S/modem/ 2>/dev/null
chmod -R a+rX \$S\"'"
rm -rf fw-stage
adb pull "$S" fw-stage >/dev/null
rm -rf fw-gpu fw-wifi fw-audio fw-ipa fw-modem
mv fw-stage/gpu fw-gpu; mv fw-stage/wifi fw-wifi; mv fw-stage/audio fw-audio
mv fw-stage/ipa fw-ipa; mv fw-stage/modem fw-modem; rmdir fw-stage
adb shell "su -c 'rm -rf $S'"
for d in fw-gpu fw-wifi fw-audio fw-ipa fw-modem fw-modem/image; do
	[ -d "$d" ] && echo "pull-firmware-root.sh: $d: $(ls -1 "$d" | wc -l | tr -d ' ') files"
done
echo "pull-firmware-root.sh: done; Wi-Fi also wants fw-wifi/mac (the radio's address) and fw-wifi/network (the network's name and passphrase)"
