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
runtime = Path(sys.argv[3])
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

# Older UN1CA runtime code repeats this exact structure. Upstream now provides
# the same structure in ksud.h; retain the original runtime logic, not two definitions.
old_struct = """struct user_arg_ptr {
#ifdef CONFIG_COMPAT
\tbool is_compat;
#endif
\tunion {
\t\tconst char __user *const __user *native;
#ifdef CONFIG_COMPAT
\t\tconst compat_uptr_t __user *compat;
#endif
\t} ptr;
};
"""
upstream_struct = hdr[hdr.index("struct user_arg_ptr {"):hdr.index("};", hdr.index("struct user_arg_ptr {")) + 3]
if upstream_struct.strip() != old_struct.strip():
    raise SystemExit("Runtime and header types differ; manual review required")
runtime_src = runtime.read_text()
if runtime_src.count(old_struct) != 1:
    raise SystemExit(f"Expected one duplicate user_arg_ptr in {runtime}, got {runtime_src.count(old_struct)}")
runtime.write_text(runtime_src.replace(old_struct, "", 1))
print("Removed only duplicate struct user_arg_ptr from retained UN1CA runtime")
