#!/bin/bash
# Build the iOS 17.0.0 kernel (the port on xnu-10002.1.13) with the common tree's build, in one command.
#
#   devices/oneplus8t/tools/build-ios17.sh -j8
#
# It expects what docs/building-ios17.md sets up: the common tree, theos with an iOS 17.0 SDK, the kernel
# tree made by ios17/apply.sh, and xnu-deps/setup.sh already run (stage 1 and 2). It does not fetch or
# install anything; it checks, then builds, then says what it got.
#
# The build is the common tree's tools/make-kernel.sh, with these three moved to the 17 tree and SDK:
#   XNU_SRC=$ROOT/xnu-src/xnu-10002.1.13
#   XNU_SDK_PATH=$ROOT/xnu-deps/sdk/iPhoneOS17.0.xnu.sdk
#   XNU_SDK_VERSION=17.0
# and KERNEL pointing at that tree's mach.development.bcm2837. Exit status 2 from make is expected and is
# judged by make-kernel.sh (the kext symbol-set checks fail on this configuration; a compile or link
# error does not pass).
set -u
HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
[ -f "$ROOT/tools/make-kernel.sh" ] || { echo "build-ios17: $ROOT is not the common tree (no tools/make-kernel.sh)" >&2; exit 1; }
TREE=$ROOT/xnu-src/xnu-10002.1.13
SDK=$ROOT/xnu-deps/sdk/iPhoneOS17.0.xnu.sdk
KERNEL=$TREE/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837

fail() { echo "build-ios17: $*" >&2; exit 1; }

[ -d "$TREE" ] || fail "no $TREE: run devices/oneplus8t/ios17/apply.sh first"
[ -d "$SDK" ] || fail "no $SDK: run xnu-deps/setup.sh --stage1 with the 17.0 SDK names (docs/building-ios17.md, step 3 and 5)"
[ -x "${THEOS:-$HOME/theos}/toolchain/linux/iphone/bin/ld" ] || fail "no theos cctools at ${THEOS:-$HOME/theos}/toolchain/linux/iphone/bin/ld"

echo "build-ios17: checking the tree against the APIs 17.0 moved"
python3 "$HERE/check-ios17-tree.py" "$TREE" || fail "the tree still calls something 17.0 removed (above)"

export XNU_SRC=$TREE
export XNU_SDK_PATH=$SDK
export XNU_SDK_VERSION=17.0
export KERNEL
echo "build-ios17: XNU_SRC=$XNU_SRC"
echo "build-ios17: SDK=$XNU_SDK_PATH ($XNU_SDK_VERSION)"
echo "build-ios17: building (exit status 2 is the kext symbol-set checks; make-kernel.sh judges it)"
# make-kernel.sh syncs drivers only for the 16.5 tree; ours are already in this tree from apply.sh
KERNEL_LOG=${KERNEL_LOG:-$ROOT/xnu-build-ios17.log}
"$ROOT/tools/make-kernel.sh" "$@"
status=$?
if [ -f "$KERNEL" ]; then
	cp -p "$KERNEL" "$ROOT/hakios-kernel"
	echo "build-ios17: kernel: $ROOT/hakios-kernel (built by tools/make-kernel.sh, status $status)"
	exit 0
fi
echo "build-ios17: no kernel was produced; the log is $KERNEL_LOG" >&2
grep -nE '(error|fatal error):' "$KERNEL_LOG" 2>/dev/null | head -20 >&2
exit 1
