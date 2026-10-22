#!/usr/bin/env python3
"""Isolate KernelSU Next from SUSFS for an enforcing boot diagnostic.

Disable all SUSFS options in the last (Apollo) defconfig fragment. The
Apollo builder appends this fragment after its base kernel defconfig.
Leave EROFS, SELinux Enforcing, KernelSU Next and other ROM options intact.
"""
from pathlib import Path
import re
import sys
if len(sys.argv) != 2:
    raise SystemExit("usage: disable_susfs.py apollo_defconfig")
p = Path(sys.argv[1])
src = p.read_text()
rx = re.compile(r"^CONFIG_(KSU_SUSFS(?:_[A-Z0-9_]+)?)=(?:y|m|[^\n]+)$", re.MULTILINE)
found = rx.findall(src)
if "KSU_SUSFS" not in found:
    raise SystemExit("Expected CONFIG_KSU_SUSFS=y in source, check input.")
out = rx.sub(lambda m: "# CONFIG_" + m.group(1) + " is not set", src)
if re.search(r"^CONFIG_KSU_SUSFS(?:_[A-Z0-9_]+)?=", out, re.MULTILINE):
    raise SystemExit("SUSFS remains enabled in Apollo config")
if "CONFIG_ALWAYS_PERMISSIVE=y" in out:
    raise SystemExit("Refusing permissive config")
p.write_text(out)
print(f"Disabled {len(found)} SUSFS config values; SELinux remains Enforcing")
