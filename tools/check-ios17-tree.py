#!/usr/bin/env python3
"""Check a tree of this port against the XNU 10002 APIs that moved -- the things the 16.5 work used and
iOS 17.0's kernel does not have. Run it on the tree ios17/apply.sh makes, and again after changing a
driver: a hit is a place that would not compile, or would call the wrong thing.

usage: tools/check-ios17-tree.py [TREE]        (default: <repo>/xnu-src/xnu-10002.1.13)

What it looks for, and why each one:

  UIO_STACKBUF(                    16.5's macro for a uio stack buffer. 17.0 has uio_stackbuf_t instead;
                                   the rebase dropped it in 37 places -- any hit is new code written
                                   against the old tree.
  set_security_token_task_internal XNU 17 removed it (16.5 had it in bsd/kern/kern_prot.c); its job is
                                   kauth_cred_proc_update()/task_set_uniqueid() now.
  persona_proc_adopt(...cred)      17 adopts a persona through a credential-model block, not a ready-made
                                   credential.
  configure_misc_apple_regs()      the parentheses are empty: 17's takes (bool is_boot_cpu).
  ios17 TODO(port)                 should be there exactly once: it is the one place the rebase gave up a
                                   behaviour (jetsam sized on sane_size, not max_mem).
"""
import os
import re
import sys

PATTERNS = [
    (r'\bUIO_STACKBUF\s*\(', 0, "16.5's uio macro; use uio_stackbuf_t (17.0's)"),
    (r'\bset_security_token_task_internal\b', 0, "removed in 17.0; use kauth_cred_proc_update()/task_set_uniqueid()"),
    (r'persona_proc_adopt\s*\([^;]*,\s*cred\s*\)', 0, "17.0 adopts through a credential-model block"),
    (r'configure_misc_apple_regs\s*\(\s*\)', 0, "17.0's takes (bool is_boot_cpu)"),
    (r'ios17 TODO\(port\)', 1, "the rebase's one known behaviour gap; exactly one line expected"),
]
COMMENT = re.compile(r'^\s*(\*|//|/\*)')


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "xnu-src", "xnu-10002.1.13")
    if not os.path.isdir(root):
        sys.exit("check-ios17-tree: no tree at %s (ios17/apply.sh makes one)" % root)
    counts = {p: 0 for p, _, _ in PATTERNS}
    hits = {p: [] for p, _, _ in PATTERNS}
    files = 0
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "BUILD")]
        for name in names:
            if not name.endswith((".c", ".h", ".cpp")):
                continue
            files += 1
            path = os.path.join(base, name)
            try:
                lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, 1):
                for pat, _want, _why in PATTERNS:
                    if re.search(pat, line):
                        if COMMENT.match(line) and "TODO" not in pat:
                            continue
                        counts[pat] += 1
                        if len(hits[pat]) < 5:
                            hits[pat].append("%s:%d: %s" % (os.path.relpath(path, root), line_no, line.strip()))
    bad = 0
    print("check-ios17-tree: %s (%d source files)" % (root, files))
    for pat, want, why in PATTERNS:
        got = counts[pat]
        ok = got == want
        print("  %-6s %-4d want %-2d  %s" % ("ok" if ok else "FAIL", got, want, why))
        for h in hits[pat]:
            print("        " + h)
        if not ok:
            bad += 1
    if bad:
        print("check-ios17-tree: %d pattern(s) not as expected" % bad)
        return 1
    print("check-ios17-tree: clean -- nothing in the tree calls an API that 17.0 removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
