#!/bin/bash
# Pull this phone's own firmware out of its Android into the fw-*/ directories at the top of the
# repository (never committed: it is the vendor's). The phone is on adb, in Android.
#
# What this phone has, from its own /vendor/firmware and /vendor/firmware_mnt (OnePlus 8T, KB2000):
#   GPU     a650_gmu.bin, a650_sqe.fw, a650_zap.mdt/b00..b02 (Adreno 650)
#   Wi-Fi   QCA6390: /vendor/firmware/wlan/qca_cld/** (the board data), and the radio's image in
#           /vendor/firmware_mnt/image/wpss.*
#   audio   /vendor/firmware_mnt/image/adsp.* (the audio DSP; the battery's level comes through it too)
#   modem   /vendor/firmware_mnt/image/modem.* and the image/ directory itself (the modem's TFTP files)
#   IPA     /vendor/firmware/ipa_fws.* (soc_ipa_fw=ipa_fws names it)
#
# /vendor/firmware_mnt is root-only on this unit: if every file below is reported "not on the phone",
# use pull-firmware-root.sh, which does the same pull through su.
set -e
cd "$(dirname "$0")"
pull() { # DIR SOURCE...  (missing files are told, not fatal)
	local dir=$1; shift
	mkdir -p "$dir"
	for f in "$@"; do adb pull "$f" "$dir/" >/dev/null 2>&1 || echo "pull-firmware.sh: $f: not on the phone"; done
	echo "pull-firmware.sh: $dir: $(ls -1 "$dir" | wc -l | tr -d ' ') files"
}
adb get-state >/dev/null
pull fw-gpu /vendor/firmware/a650_gmu.bin /vendor/firmware/a650_sqe.fw /vendor/firmware/a650_zap.mdt /vendor/firmware/a650_zap.b00 /vendor/firmware/a650_zap.b01 /vendor/firmware/a650_zap.b02
pull fw-wifi $(for i in mdt b00 b01 b02 b03 b04 b05 b06 b07 b08 b09 b10 b11 b12 b13 b14 b15 b16 b17 b18 b19 b20 b21 b22 b23 b24 b25 b26 b27 b28; do echo /vendor/firmware_mnt/image/wpss.b$i; done) /vendor/firmware_mnt/image/wpss.mdt
mkdir -p fw-wifi/qca_cld
adb pull /vendor/firmware/wlan/qca_cld fw-wifi/qca_cld >/dev/null 2>&1 && echo "pull-firmware.sh: fw-wifi/qca_cld: the radio's board data" || echo "pull-firmware.sh: /vendor/firmware/wlan/qca_cld: not on the phone (root only?)"
pull fw-audio /vendor/firmware_mnt/image/adsp.mdt $(for i in $(seq -w 0 30); do echo /vendor/firmware_mnt/image/adsp.b$i; done)
pull fw-ipa /vendor/firmware/ipa_fws.mdt /vendor/firmware/ipa_fws.b00 /vendor/firmware/ipa_fws.b01 /vendor/firmware/ipa_fws.b02 /vendor/firmware/ipa_fws.b03 /vendor/firmware/ipa_fws.b04
pull fw-modem /vendor/firmware_mnt/image/modem.mdt $(for i in $(seq -w 0 29); do echo /vendor/firmware_mnt/image/modem.b$i; done)
mkdir -p fw-modem/image && adb pull /vendor/firmware_mnt/image fw-modem/ >/dev/null 2>&1 && echo "pull-firmware.sh: fw-modem/image: the modem's own files (TFTP)"
echo "pull-firmware.sh: done; Wi-Fi also wants fw-wifi/mac (the radio's address) and fw-wifi/network (the network's name and passphrase)"
