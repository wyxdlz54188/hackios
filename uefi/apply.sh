#!/bin/bash
# This phone's UEFI, through HakiOS's UEFI tree: uefi/apply.sh of the common repository (Mu-Silicium
# at its BASE + HakiOS's patch and banner), with the OnePlus 8T's platform. That platform is the one
# Mu-Silicium already carries, kebabPkg -- this unit is a kebab board (README.md here says how that was
# established, and what the two memory windows worth watching are). There is no platform of our own to
# copy in, so this script is the one line that names the device, and nothing else.
#
# usage: uefi/apply.sh            (from this device repository)
set -e
exec "$(dirname "$(readlink -f "$0")")/../../../uefi/apply.sh" kebab
