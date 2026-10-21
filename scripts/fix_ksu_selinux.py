#!/usr/bin/env python3
"""Backport KernelSU Next's AVC sequence reset to pre-SELINUX_STATE Linux 4.9.

On the target kernel 4.9.337, KSU_COMPAT_USE_SELINUX_STATE is unset.
The previous Eend15 code reset the AVC cache with seqno=0.
Preserve that working behavior and use the new seqno only where available.
"""
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()
needle = "\tu32 seqno = selinux_state.ss ? ++selinux_state.ss->latest_granting : 1;"
assert s.count(needle) == 1, "Unexpected rules.c; manual inspection required"
replacement = """#ifdef KSU_COMPAT_USE_SELINUX_STATE
\tu32 seqno = selinux_state.ss ? ++selinux_state.ss->latest_granting : 1;
#else
\tu32 seqno = 0;
#endif"""
p.write_text(s.replace(needle, replacement, 1))
print("Applied guarded Linux 4.9 SELinux AVC sequence compatibility")
