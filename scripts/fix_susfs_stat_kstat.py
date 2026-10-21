#!/usr/bin/env python3
"""Adapt SUSFS v2.3 KSTAT to UN1CA's backported statx/vfs_getattr_nosec API.

The generic SUSFS kernel-4.9-v2 patch assumes vfs_getattr_nosec(path, stat),
but Eend15's 4.9.337 has a backport accepting (const path*, kstat*, u32,
unsigned int). Preserve all four arguments and request_mask semantics.
"""
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()
def once(a,b):
    global s
    c=s.count(a)
    if c != 1:
        raise SystemExit(f"Expected exactly once ({c}): {a[:120]!r}")
    s=s.replace(a,b,1)

old_extern = """#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
extern void susfs_sus_ino_for_generic_fillattr(unsigned long ino, struct kstat *stat);
#endif"""
new_extern = """#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
extern bool susfs_is_inode_sus_kstat(struct inode *inode, bool *out_is_fuse);
extern void susfs_sus_kstat_spoof_generic_fillattr(struct inode *inode,
                                                  struct kstat *stat,
                                                  u32 result_mask);
#endif"""
once(old_extern,new_extern)
legacy = """#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
\tif (likely(current->susfs_task_state & TASK_STRUCT_NON_ROOT_USER_APP_PROC) &&
\t\t\tunlikely(inode->i_state & INODE_STATE_SUS_KSTAT)) {
\t\tsusfs_sus_ino_for_generic_fillattr(inode->i_ino, stat);
\t\tstat->mode = inode->i_mode;
\t\tstat->rdev = inode->i_rdev;
\t\tstat->uid = inode->i_uid;
\t\tstat->gid = inode->i_gid;
\t\treturn;
\t}
#endif
"""
once(legacy,"")

start = """\tstruct inode *inode = d_backing_inode(path->dentry);

\tmemset(stat, 0, sizeof(*stat));"""
newstart = """\tstruct inode *inode = d_backing_inode(path->dentry);
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
\tbool is_fuse = false;
\tu32 susfs_result_mask = 0;
\tint susfs_getattr_err;
#endif

\tmemset(stat, 0, sizeof(*stat));"""
once(start,newstart)
original = """\trequest_mask &= STATX_ALL;
\tquery_flags &= KSTAT_QUERY_FLAGS;
\tif (inode->i_op->getattr)
\t\treturn inode->i_op->getattr(path, stat, request_mask,
\t\t\t\t\t    query_flags);

\tgeneric_fillattr(inode, stat);
\treturn 0;"""
revised = """\trequest_mask &= STATX_ALL;
\tquery_flags &= KSTAT_QUERY_FLAGS;
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
\tif (susfs_is_current_app_uid() &&
\t    susfs_is_inode_sus_kstat(inode, &is_fuse))
\t\tsusfs_result_mask = is_fuse ? STATX_SUS_KSTAT_FUSE : STATX_SUS_KSTAT;
#endif
\tif (inode->i_op->getattr) {
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
\t\tsusfs_getattr_err = inode->i_op->getattr(path, stat, request_mask, query_flags);
\t\tif (!susfs_getattr_err && susfs_result_mask)
\t\t\tsusfs_sus_kstat_spoof_generic_fillattr(inode, stat, susfs_result_mask);
\t\treturn susfs_getattr_err;
#else
\t\treturn inode->i_op->getattr(path, stat, request_mask, query_flags);
#endif
\t}

\tgeneric_fillattr(inode, stat);
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
\tif (susfs_result_mask)
\t\tsusfs_sus_kstat_spoof_generic_fillattr(inode, stat, susfs_result_mask);
#endif
\treturn 0;"""
once(original,revised)
p.write_text(s)
print("Integrated SUSFS v2.3 KSTAT with Eend15's four-argument statx path")
