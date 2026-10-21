#!/usr/bin/env python3
"""Remove incompatible ReSukiSU faccessat shim from SUSFS v2.3 partial port.

The UN1CA source already hooks the Linux 4.9 faccessat path using KernelSU Next:
  ksu_handle_faccessat(int*, const char __user**, int*, int*)
SUSFS's port assumes the different ReSukiSU struct-filename API and duplicates
that hook. Preserve the existing hook and original user_path_at() call.
"""
from pathlib import Path
import re
import sys

p=Path(sys.argv[1])
src=p.read_text()
regex_decl = (
    r'\n#ifdef CONFIG_KSU_SUSFS\n'
    r'/\* SukiSU-Ultra keeps ksu_su_compat_enabled as a plain bool, not a static key\. \*/\n'
    r'extern bool ksu_su_compat_enabled __read_mostly;\n'
    r'extern bool __ksu_is_allow_uid_for_current\(uid_t uid\);\n'
    r'extern int ksu_handle_faccessat\(int \*dfd, struct filename \*\*filename, int \*mode,\n'
    r'\s*int \*__unused_flags\);\n'
    r'#endif\n'
)
src, count = re.subn(regex_decl,"\n",src,count=1)
if count != 1:
    raise SystemExit(f"Expected one conflicting ReSukiSU faccessat declaration, got {count}")

pat_block = (r'retry:\n#ifdef CONFIG_KSU_SUSFS\n'
             r'\s*fname = getname_flags\(filename, lookup_flags, NULL\);'
             r'.*?\n#else\n'
             r'\s*res = user_path_at\(dfd, filename, lookup_flags, &path\);\n'
             r'#endif\n')
replacement="retry:\n\tres = user_path_at(dfd, filename, lookup_flags, &path);\n"
src, count = re.subn(pat_block,replacement,src,count=1,flags=re.DOTALL)
if count != 1:
    raise SystemExit(f"Expected exactly one SUSFS faccessat override, got {count}")
if 'ksu_handle_faccessat(&dfd, &filename, &mode, NULL);' not in src:
    raise SystemExit("Original UN1CA KernelSU Next manual faccessat hook was lost")
p.write_text(src)
print("Kept original UN1CA KernelSU Next faccessat hook; discarded incompatible ReSukiSU version")
