#!/usr/bin/env python3
"""Update inotify fdinfo SUSFS KSTAT to 2.3 inode-based spoofing.

Avoid obsolete task state / inode state checks. Retain original inotify ABI,
and use the original show_mark_fhandle in both successful and normal cases.
"""
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);src=p.read_text()
inc="#include <linux/susfs_def.h>"
if src.count(inc)!=1:raise SystemExit("Expected SUSFS include once")
# The original port includes this header only for SUS_MOUNT, but the
# SUS_KSTAT inotify hook also calls its static inline UID predicate.
# Without this guard expansion the no-mount Enforcing build fails with
# an implicit declaration of susfs_is_current_app_uid().
old_inc="#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n#include <linux/susfs_def.h>\n#endif"
new_inc="#if defined(CONFIG_KSU_SUSFS_SUS_MOUNT) || defined(CONFIG_KSU_SUSFS_SUS_KSTAT)\n#include <linux/susfs_def.h>\n#endif"
if src.count(old_inc)!=1:raise SystemExit("Unexpected original SUSFS header guard")
src=src.replace(old_inc,new_inc,1)
decl="#if defined(CONFIG_PROC_FS)"
add="""#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
extern bool susfs_is_inode_sus_kstat(struct inode *inode, bool *out_is_fuse);
extern void susfs_sus_kstat_spoof_inotify_fdinfo(unsigned long *out_target_ino,
                                                  dev_t *out_target_dev);
#endif

"""
if src.count(decl)!=1:raise SystemExit("Missing inotify declaration insertion point")
src=src.replace(decl,add+decl,1)
start="#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n\t\tu32 mask = inotify_mark_user_mask(mark);"
end="#endif\n\t\tseq_printf(m, \"inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 \","
if src.count(start)!=1 or src.count(end)!=1:raise SystemExit("Legacy inotify KSTAT hook boundary mismatch")
a=src.index(start);b=src.index(end,a)+len("#endif\n")
replacement="""#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
        if (susfs_is_current_app_uid()) {
            bool is_fuse = false;
            if (susfs_is_inode_sus_kstat(inode, &is_fuse)) {
                unsigned long ino = inode->i_ino;
                dev_t dev = inode->i_sb->s_dev;
                susfs_sus_kstat_spoof_inotify_fdinfo(&ino, &dev);
                seq_printf(m, "inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 ",
                           inode_mark->wd, ino, dev, inotify_mark_user_mask(mark));
                show_mark_fhandle(m, inode);
                seq_putc(m, '\\n');
                iput(inode);
                return;
            }
        }
#endif
"""
src=src[:a]+replacement+src[b:]
if "TASK_STRUCT_NON_ROOT_USER_APP_PROC" in src or "INODE_STATE_SUS_KSTAT" in src:
    raise SystemExit("Unexpected stale SUSFS inotify state field")
p.write_text(src)
print("Migrated inotify KSTAT to SUSFS v2.3 helper")
