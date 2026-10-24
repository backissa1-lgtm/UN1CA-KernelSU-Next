#!/usr/bin/env python3
"""Repair the exact Linux 4.9 KernelSU bounded SELinux transition mismatch.

Original Eend15/UN1CA code special-cases init -> u:r:su:s0 on nosuid
filesystems. KernelSU Next invokes ksud as u:r:ksu:s0, so the exception
never matches and security_bounded_transition() can return -EACCES.
Android init then reports "cannot execv('/data/adb/ksud'): Permission denied".

This patch only recognizes init -> KernelSU Next's actual ksu domain,
preserving the existing Android SELinux policy, transition conditions
and global Enforcing mode. No broad denial bypass and no permissive mode.
"""
from pathlib import Path
import sys

OLD = (
    '#ifdef CONFIG_KSU\n'
    '\tif (!ksu_sid) {\n'
    '            security_secctx_to_secid("u:r:su:s0", strlen("u:r:su:s0"), &ksu_sid);\n'
    '\t}\n'
)
NEW = (
    '#ifdef CONFIG_KSU\n'
    '\t/* The current KernelSU Next daemon runs in u:r:ksu:s0, not u:r:su:s0.\n'
    '\t * Keep this nosuid exception limited to init -> KernelSU Next.\n'
    '\t */\n'
    '\tif (!ksu_sid) {\n'
    '            security_secctx_to_secid("u:r:ksu:s0", strlen("u:r:ksu:s0"), &ksu_sid);\n'
    '\t}\n'
)

def patch(src: str) -> str:
    if src.count(OLD) != 1:
        raise ValueError("Unexpected SELinux hooks layout or exception already changed")
    if src.count('security_bounded_transition(old_tsec->sid, new_tsec->sid)') != 1:
        raise ValueError("Bounded SELinux transition check changed")
    if src.count('if (rc == 0 && new_tsec->sid == ksu_sid) {') != 1:
        raise ValueError("Existing init-to-KernelSU-only restriction missing")
    out = src.replace(OLD, NEW, 1)
    if 'CONFIG_SECURITY_SELINUX_DISABLE=y' in out or 'CONFIG_ALWAYS_PERMISSIVE=y' in out:
        raise ValueError("Unexpected permissive setting")
    if out.count('security_bounded_transition(old_tsec->sid, new_tsec->sid)') != 1:
        raise ValueError("SELinux bounded transition was removed")
    return out

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or (len(sys.argv)==3 and sys.argv[2]!="--verify"):
        raise SystemExit("usage: fix_ksud_selinux_transition.py security/selinux/hooks.c [--verify]")
    p=Path(sys.argv[1])
    s=p.read_text()
    if len(sys.argv)==3:
        if s.count(NEW)!=1 or s.count(OLD)!=0:
            raise SystemExit("KernelSU Next domain exception not installed")
        print("Verified: bounded transition only allows init -> u:r:ksu:s0")
    else:
        p.write_text(patch(s))
        print("Fixed UN1CA Linux 4.9 SELinux exception for init -> KernelSU Next ksud")
