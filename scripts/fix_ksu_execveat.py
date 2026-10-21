#!/usr/bin/env python3
"""Reconcile Eend15's retained init.c with upstream KernelSU-Next's typed ksud.h.

This is a targeted source compatibility patch, not a fake version bump.
Abort if the source signature changes unexpectedly.
"""
import re
import sys
from pathlib import Path

init = Path(sys.argv[1])
header = Path(sys.argv[2])
src = init.read_text()
hdr = header.read_text()

if "struct user_arg_ptr *argv" not in hdr or "ksu_handle_execveat_ksud" not in hdr:
    raise SystemExit("Upstream header lacks the expected typed execveat declaration")

pat = (r"extern int ksu_handle_execveat_ksud\(int \*fd,\s*"
       r"struct filename \*\*filename_ptr,\s*"
       r"void \*argv,\s*void \*envp,\s*int \*flags\);\s*")
src, removed = re.subn(pat, "", src, count=1)
if removed != 1:
    raise SystemExit(f"Expected exactly one stale execveat declaration, got {removed}")

old = "ksu_handle_execveat_ksud(fd, filename_ptr, argv, envp, flags);"
new = ("ksu_handle_execveat_ksud(fd, filename_ptr,\n"
       "                                (struct user_arg_ptr *)argv,\n"
       "                                (struct user_arg_ptr *)envp, flags);")
if src.count(old) != 1:
    raise SystemExit("Original init.c execveat invocation no longer matches")
src = src.replace(old, new, 1)
init.write_text(src)
print("Preserved UN1CA init.c, corrected typed KernelSU-Next execveat bridge")
