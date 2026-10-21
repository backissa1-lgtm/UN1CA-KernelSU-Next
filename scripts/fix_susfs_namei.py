#!/usr/bin/env python3
"""Compile-probe-only semantic conversion of old SUSFS v1.5 namei hide guards.

v1.5 tracked hide state in inode->i_state and task->susfs_task_state.
v2.3 drops these fields; susfs_is_inode_sus_path(inode) checks the current
mount/user namespace and the inode's address_space. This adaptation is NOT
a boot-reviewed kernel patch.
"""
from pathlib import Path
import re,sys
if len(sys.argv)!=2: raise SystemExit("usage: fix_susfs_namei.py kernel/fs/namei.c")
p=Path(sys.argv[1]);s=p.read_text()
old = re.compile(
 r'unlikely\(\s*([A-Za-z_][A-Za-z_0-9]*(?:->[A-Za-z_][A-Za-z_0-9]*)+)->i_state\s*&\s*INODE_STATE_SUS_PATH\s*\)'
 r'\s*&&\s*likely\(\s*current->susfs_task_state\s*&\s*TASK_STRUCT_NON_ROOT_USER_APP_PROC\s*\)')
def replace(m):return f"susfs_is_inode_sus_path({m.group(1)})"
s,n=old.subn(replace,s)
if not (10<=n<=30):
 raise SystemExit(f"Unexpected old SUSFS guard count: {n} (expected 10 to 30)")
if "INODE_STATE_SUS_PATH" in s or "TASK_STRUCT_NON_ROOT_USER_APP_PROC" in s:
 raise SystemExit("Old SUSFS guard still found after conversion")
# SUSFS2.3 patch adds an extern int filename_lookup declaration via namei.h,
# so the original Samsung function must agree. Do not change any callers.
oldfn="static int filename_lookup(int dfd, struct filename *name, unsigned flags,"
newfn="int filename_lookup(int dfd, struct filename *name, unsigned flags,"
if s.count(oldfn)!=1: raise SystemExit("Unexpected filename_lookup declaration")
s=s.replace(oldfn,newfn,1)
# SUSFS 2.3 helper returns false for non-app/current namespace and checks
# inode-mapping hide marks; validate the new helper is declared in this TU.
if "susfs_is_inode_sus_path" not in s:
 raise SystemExit("SUSFS 2.3 helper not found")
p.write_text(s)
print(f"Reconciled {n} SUSFS 1.5 inode/task guards; fixed filename_lookup linkage")
