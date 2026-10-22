#!/usr/bin/env python3
"""Temporarily disable SUSFS 2.3 mount hiding for a targeted bootloop test.

Keep KernelSU Next, SUSFS 2.3 core, path, KSTAT, and every unrelated kernel
configuration unchanged. This does not switch SELinux to Permissive.
"""
from pathlib import Path
import sys
if len(sys.argv) != 2:
    raise SystemExit("Usage: disable_susfs_mount.py candidate/arch/arm64/configs/apollo_defconfig")
p = Path(sys.argv[1])
s = p.read_text()
old = "CONFIG_KSU_SUSFS_SUS_MOUNT=y"
if s.count(old) != 1:
    raise SystemExit(f"Expected exactly one enabled SUSFS mount option, got {s.count(old)}")
s = s.replace(old, "# CONFIG_KSU_SUSFS_SUS_MOUNT is not set", 1)
if s.count("CONFIG_KSU_SUSFS=y") != 1:
    raise SystemExit("SUSFS core must remain enabled")
if "CONFIG_ALWAYS_PERMISSIVE=y" in s:
    raise SystemExit("Refusing Permissive configuration")
p.write_text(s)
print("Diagnostic: SUSFS 2.3 mount hiding disabled; core remains enabled; SELinux Enforcing")
