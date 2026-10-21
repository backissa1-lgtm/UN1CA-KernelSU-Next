#!/usr/bin/env python3
"""Reconcile v2.3 SUSFS port with preexisting UN1CA KernelSU Next manual hooks.

The 4.9 SUSFS patch ships ReSukiSU-specific callbacks duplicating UN1CA's
execve, stat and reboot hooks. Avoid invoking root callbacks twice.
"""
from pathlib import Path
import re,sys

root=Path(sys.argv[1])
def edit(name, transformations, invariants):
    p=root/name
    s=p.read_text()
    for before,after,flags in transformations:
        s,count=re.subn(before,lambda _:after,s,count=1,flags=flags)
        if count!=1: raise SystemExit(f"{name}: expected one matching block, got {count}: {before[:50]}")
    for invariant in invariants:
        if invariant not in s: raise SystemExit(f"{name}: missing original UN1CA hook: {invariant}")
    p.write_text(s)
    print("Preserved UN1CA manual hook:",name)

# Exec: remove ReSukiSU externs and duplicate callback after early IS_ERR.
edit("fs/exec.c",[
 (r'\n#ifdef CONFIG_KSU_SUSFS\n/\* SukiSU-Ultra keeps ksu_su_compat_enabled as a plain bool, not a static key\. \*/'
  r'.*?\n#endif\n\n/\*', '\n/*',re.DOTALL),
 (r'\n#ifdef CONFIG_KSU_SUSFS\n\tif \(likely\(susfs_is_current_proc_no_su\(\)\)\) \{'
  r'.*?\norig_flow:\n#endif\n', '\n',re.DOTALL)
],["if (unlikely(ksu_execveat_hook))","ksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);"])

# Stat: keep signature for Linux 4.9 const char __user* and original user_path_at.
edit("fs/stat.c",[
 (r'retry:\n#ifdef CONFIG_KSU_SUSFS\n.*?\n#else\n'
  r'\terror = user_path_at\(dfd, filename, lookup_flags, &path\);\n#endif\n',
  'retry:\n\terror = user_path_at(dfd, filename, lookup_flags, &path);\n',re.DOTALL)
],["ksu_handle_stat(&dfd, &filename, &flags);"])

# Reboot: remove duplicate pre-namespace capability invocation.
edit("kernel/reboot.c",[
 (r'\n#ifdef CONFIG_KSU_SUSFS\n\tret = ksu_handle_sys_reboot\(magic1, magic2, cmd, &arg\);'
  r'.*?\norig_flow:\n#endif\n', '\n', re.DOTALL)
],["if (system_state == SYSTEM_RUNNING)","ksu_handle_sys_reboot(magic1, magic2, cmd, &arg);"])
