#!/usr/bin/env python3
"""Migrate two Samsung dcache SUSFS1.5 inode/task checks to SUSFS2.3."""
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
old="unlikely(dentry->d_inode->i_state & INODE_STATE_SUS_PATH) && likely(current->susfs_task_state & TASK_STRUCT_NON_ROOT_USER_APP_PROC)"
new="susfs_is_inode_sus_path(dentry->d_inode)"
if s.count(old)!=2:
    raise SystemExit(f"Expected two old dcache path guards; found {s.count(old)}")
s=s.replace(old,new)
incl="#include <linux/susfs_def.h>"
if s.count(incl)!=1:raise SystemExit("Unexpected dcache SUSFS include")
s=s.replace(incl,incl+"\nextern bool susfs_is_inode_sus_path(struct inode *inode);",1)
p.write_text(s)
print("Migrated both dcache inode checks to SUSFS v2.3 helper")
