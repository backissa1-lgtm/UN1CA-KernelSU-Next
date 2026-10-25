#!/usr/bin/env python3
"""Fix KernelSU allowlist boot restoration on Linux 4.9 (SM-G965F).

The legacy KernelSU loader wrongly calls the Linux >=4.14 kernel_read
signature on a 4.9.337 kernel. Its writer already uses the compatibility
shim. Change only the three reads of the on-disk allowlist, leaving
all authorization checks, record structure and saved policy unchanged.

Can be re-run safely; --verify requires the fix to already be applied.
"""
from pathlib import Path
import sys

OLD = (
    "kernel_read(fp, &magic, sizeof(magic), &off)",
    "kernel_read(fp, &version, sizeof(version), &off)",
    "kernel_read(fp, &profile, app_profile_size, &off)",
)
NEW = tuple("ksu_kernel_read_compat" + x[len("kernel_read"):] for x in OLD)

def main():
    verify = "--verify" in sys.argv[1:]
    paths = [x for x in sys.argv[1:] if x != "--verify"]
    if len(paths) != 1:
        raise SystemExit("usage: fix_ksu_allowlist_persistence.py [--verify] path/to/allowlist.c")
    p = Path(paths[0])
    src = p.read_text()
    if '#include "compat/kernel_compat.h"' not in src:
        raise SystemExit("Missing kernel_compat header; refusing to alter source")
    for old, new in zip(OLD, NEW):
        raw = src.count(old)
        patched = src.count(new)
        if raw + patched != 1:
            raise SystemExit(
                f"Expected exactly one call in allowlist loader: {old}; "
                f"raw={raw}, corrected={patched}"
            )
        if verify and raw:
            raise SystemExit(f"Unpatched allowlist loader: {old}")
        if raw:
            src = src.replace(old, new)
    if not verify:
        p.write_text(src)
    if not all(src.count(new) == 1 for new in NEW):
        raise SystemExit("Validation failed: all three reads must be corrected")
    print("PASS: all three KernelSU allowlist reads use the Linux 4.9 compatibility wrapper")

if __name__ == "__main__":
    main()
