#!/usr/bin/env python3
"""Delete obsolete ReSukiSU init-rc fstat injection not provided by KernelSU Next.

The pinned KernelSU Next legacy driver already has its own boot/runtime
integration and does not define ksu_is_init_rc_hook_enabled or
ksu_handle_vfs_fstat. Preserve Samsung's original vfs_fstat semantics.
"""
from pathlib import Path
import re
import sys

p=Path(sys.argv[1]);s=p.read_text()
pat=(r'#ifdef CONFIG_KSU_SUSFS\n'
     r'extern struct static_key_true ksu_is_init_rc_hook_enabled;\n'
     r'extern void ksu_handle_vfs_fstat\(int fd, loff_t \*kstat_size_ptr\);\n'
     r'#endif\n')
s,n=re.subn(pat,"",s,count=1)
if n!=1:raise SystemExit(f"Expected obsolete initrc stat declaration once, got {n}")
pat=(r'#ifdef CONFIG_KSU_SUSFS\n'
     r'\s*if \(static_branch_unlikely\(&ksu_is_init_rc_hook_enabled\)\)\n'
     r'\s*ksu_handle_vfs_fstat\(fd, &stat->size\);\n'
     r'#endif\n')
s,n=re.subn(pat,"",s,count=1)
if n!=1:raise SystemExit(f"Expected obsolete initrc fstat call once, got {n}")
if 'ksu_is_init_rc_hook_enabled' in s:raise SystemExit("Removed field still in source")
p.write_text(s)
print("Removed obsolete ReSukiSU init-rc fstat callback; Samsung vfs_fstat preserved")
