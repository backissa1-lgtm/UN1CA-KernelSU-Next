#!/usr/bin/env python3
"""Make ksud available at Android post-fs-data on legacy UN1CA kernel-only ZIPs.

The ROM's October 2026 init bootstrap prepares /data/adb/ksud before the
KernelSU post-fs-data action. Our G965F kernel-only ZIP deliberately preserves
the existing ROM/ramdisk, which might lack that ROM-side fix. Mirror the tested
UN1CA 'mkdir/copy/chmod/chown' init commands in the *injected* KernelSU rc
immediately before ksud post-fs-data, without altering SELinux mode or the
kernel's original manager/zygote/execve hooks.

This fixes the missing-early-daemon prerequisite; it cannot by itself prove
that init parses the injection or that userspace module execution succeeds.
"""
from pathlib import Path
import sys

BOOTSTRAP = (
    '\t"    mkdir /data/adb 0700 root root\\n"\n'
    '\t"    copy /system/bin/ksud /data/adb/ksud\\n"\n'
    '\t"    chmod 0755 /data/adb/ksud\\n"\n'
    '\t"    chown root root /data/adb/ksud\\n"\n'
)

POST_FS = '\t"on post-fs-data\\n"'
EXEC = '\t"    exec u:r:" KERNEL_SU_DOMAIN ":s0 root -- " KSUD_PATH " post-fs-data\\n"'

def patch(text):
    if text.count(POST_FS) != 1 or text.count(EXEC) != 1:
        raise ValueError("Unexpected KernelSU init rc layout")
    if "#define MODULE_RC_PATH" not in text:
        raise ValueError("KernelSU module init rc support is absent")
    if "KERNEL_SU_RC[]" not in text:
        raise ValueError("KernelSU embedded rc initializer not found")
    if "CONFIG_ALWAYS_PERMISSIVE" in text:
        raise ValueError("Refusing source with forced permissive mode")
    before, after = text.split(EXEC)
    if POST_FS not in before:
        raise ValueError("No post-fs-data trigger before daemon exec")
    if BOOTSTRAP in before:
        return text
    if "    copy /system/bin/ksud /data/adb/ksud" in text:
        raise ValueError("Unexpected partial or duplicate daemon preparation")
    result = before + BOOTSTRAP + EXEC + after
    assert result.count(EXEC) == 1
    assert result.index(POST_FS) < result.index(BOOTSTRAP) < result.index(EXEC)
    assert result.count("    copy /system/bin/ksud /data/adb/ksud") == 1
    return result

def main():
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "--verify"):
        raise SystemExit("Usage: fix_ksud_bootstrap.py KERNEL_SU_KSUD_INTEGRATION_C [--verify]")
    file = Path(sys.argv[1])
    original = file.read_text()
    modified = patch(original)
    if len(sys.argv) == 3:
        if modified != original or BOOTSTRAP not in modified:
            raise SystemExit("KernelSU early daemon bootstrap is not installed")
        print("Verified: ksud prepared before post-fs-data in enforcing injected init rc")
    else:
        if modified == original:
            raise SystemExit("No change made; expected unpatched source")
        file.write_text(modified)
        print("Inserted tested UN1CA early ksud preparation before KernelSU post-fs-data")
if __name__ == "__main__":
    main()
