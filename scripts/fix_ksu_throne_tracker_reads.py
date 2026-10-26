#!/usr/bin/env python3
"""Fix both Linux 4.9-incompatible packages.list kernel_read calls.

The legacy KernelSU Next source assumes the Linux 4.14 kernel_read ABI in
throne_tracker.c; the 4.9 adapter already exists in kernel/compat.
"""
from pathlib import Path
import sys

CALLS = (
    "kernel_read(fp, &chr, sizeof(chr), &pos)",
    "kernel_read(fp, buf, sizeof(buf) - 1, &line_start)",
)
HEADER = '#include "compat/kernel_compat.h"'

def main():
    verify = "--verify" in sys.argv[1:]
    paths = [arg for arg in sys.argv[1:] if arg != "--verify"]
    if len(paths) != 1:
        raise SystemExit("usage: fix_ksu_throne_tracker_reads.py [--verify] path")
    p = Path(paths[0])
    src = p.read_text()
    if HEADER not in src and not verify:
        anchor = '#include "ksu.h"\n'
        if src.count(anchor) != 1:
            raise SystemExit("Unexpected KernelSU tracker includes")
        src = src.replace(anchor, anchor + HEADER + "\n", 1)
    if HEADER not in src:
        raise SystemExit("KernelSU compat header missing")
    for old in CALLS:
        new = "ksu_kernel_read_compat" + old[len("kernel_read"):]
        if src.count(old) + src.count(new) != 1:
            raise SystemExit("Unexpected kernel read call count: " + old)
        if verify and old in src:
            raise SystemExit("Unpatched kernel_read: " + old)
        src = src.replace(old, new)
    if "kernel_read(" in src:
        raise SystemExit("Unexpected direct kernel_read remaining")
    if not verify:
        p.write_text(src)
    print("Linux 4.9 package UID tracker read calls verified" if verify else "Two KernelSU tracker read calls corrected")

if __name__ == "__main__":
    main()
