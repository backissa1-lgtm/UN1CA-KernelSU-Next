#!/usr/bin/env python3
"""Port older SUSFS 1.5.5 VFS statfs and proc-fd hooks to SUSFS 2.3.

Use v2.3 inode/mount helpers, preserve normal kernel control flow and
avoid leaking superblock references in vfs_ustat. These conversions must
be validated by kernel CI and a separate device boot test.
"""
from pathlib import Path
import sys
root=Path(sys.argv[1])
def edit(rel,fn):
 p=root/rel
 before=p.read_text()
 after=fn(before)
 if after==before:raise SystemExit(f"{rel}: patch made no changes")
 p.write_text(after)
 print("Ported",rel)
def one(s,a,b,label):
 count=s.count(a)
 if count!=1:raise SystemExit(f"{label}: expected exactly one occurrence, got {count}")
 return s.replace(a,b,1)
def statfs(s):
 s=one(s,"#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n#include <linux/susfs_def.h>\n#include \"mount.h\"\n#endif",
 """#ifdef CONFIG_KSU_SUSFS
#include <linux/susfs_def.h>
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
#include "mount.h"
extern struct vfsmount *susfs_get_non_sus_vfsmnt_from_vfsmnt(struct vfsmount *vfsmnt);
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
extern bool susfs_is_inode_sus_kstat(struct inode *inode, bool *out_is_fuse);
extern int susfs_sus_kstat_spoof_vfs_statfs(struct inode *inode, struct kstatfs *buf,
        bool *is_fuse);
#endif""","statfs includes")
 needle="int vfs_statfs(struct path *path, struct kstatfs *buf)\n{"
 head="""#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
static int susfs_statfs_by_dentry(struct dentry *dentry, struct kstatfs *buf,
                                 bool *is_fuse)
{
    int retval;
    if (!dentry->d_sb->s_op->statfs)
        return -ENOSYS;
    memset(buf, 0, sizeof(*buf));
    retval = security_sb_statfs(dentry);
    if (retval)
        return retval;
    if (!susfs_sus_kstat_spoof_vfs_statfs(d_backing_inode(dentry), buf, is_fuse))
        return buf->f_frsize ? 0 : (buf->f_frsize = buf->f_bsize, 0);
    retval = dentry->d_sb->s_op->statfs(dentry, buf);
    if (!retval && !buf->f_frsize)
        buf->f_frsize = buf->f_bsize;
    return retval;
}
#endif

"""
 s=one(s,needle,head+needle,"statfs helper")
 old="""int vfs_statfs(struct path *path, struct kstatfs *buf)
{
\tint error;
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
\tstruct mount *mnt;

\tmnt = real_mount(path->mnt);
\tif (likely(current->susfs_task_state & TASK_STRUCT_NON_ROOT_USER_APP_PROC)) {
\t\tfor (; mnt->mnt_id >= DEFAULT_SUS_MNT_ID; mnt = mnt->mnt_parent) {}
\t}
\terror = statfs_by_dentry(mnt->mnt.mnt_root, buf);
\tif (!error)
\t\tbuf->f_flags = calculate_f_flags(&mnt->mnt);
\treturn error;
#else
\terror = statfs_by_dentry(path->dentry, buf);
\tif (!error)
\t\tbuf->f_flags = calculate_f_flags(path->mnt);
\treturn error;
#endif
}"""
 new="""int vfs_statfs(struct path *path, struct kstatfs *buf)
{
    int error;
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
    if (susfs_is_current_app_uid()) {
        struct inode *inode = d_backing_inode(path->dentry);
        bool is_fuse = false;
        if (inode && susfs_is_inode_sus_kstat(inode, &is_fuse)) {
            error = susfs_statfs_by_dentry(path->dentry, buf, &is_fuse);
            goto out_flags;
        }
    }
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
    if (susfs_is_current_proc_umounted()) {
        struct vfsmount *legit = susfs_get_non_sus_vfsmnt_from_vfsmnt(path->mnt);
        if (legit) {
            struct dentry *root = legit->mnt_root;
            error = statfs_by_dentry(root, buf);
            if (!error)
                buf->f_flags = calculate_f_flags(legit);
            dput(root);
            mntput(legit);
            return error;
        }
    }
#endif
    error = statfs_by_dentry(path->dentry, buf);
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
out_flags:
#endif
    if (!error)
        buf->f_flags = calculate_f_flags(path->mnt);
    return error;
}"""
 s=one(s,old,new,"vfs_statfs")
 old="""#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
\tif (unlikely(s->s_root->d_inode->i_state & INODE_STATE_SUS_MOUNT)) {
\t\treturn -EINVAL;
\t}
#endif
"""
 s=one(s,old,"","vfs_ustat legacy inode test")
 return s

def proc_fd(s):
 old="""#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
\tstruct mount *mnt = NULL;
#endif
"""
 s=one(s,old,"","proc fd unused mount")
 includes='#include "fd.h"\n'
 s=one(s,includes,includes+"""
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
extern int susfs_get_non_sus_mnt_id_from_mnt(struct mount *orig_mnt);
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
extern bool susfs_is_inode_sus_kstat(struct inode *inode, bool *out_is_fuse);
extern void susfs_sus_kstat_spoof_proc_fd_seq_show(int *out_target_mnt_id,
                    unsigned long *out_target_ino, dev_t target_dev);
#endif
""","proc fd prototypes")
 old="""#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
\tmnt = real_mount(file->f_path.mnt);
\tif (likely(current->susfs_task_state & TASK_STRUCT_NON_ROOT_USER_APP_PROC) &&
\t\t\tmnt->mnt_id >= DEFAULT_SUS_MNT_ID) {
\t\tfor (; mnt->mnt_id >= DEFAULT_SUS_MNT_ID; mnt = mnt->mnt_parent) { }
\t}
\tseq_printf(m, "pos:\\t%lli\\nflags:\\t0%o\\nmnt_id:\\t%i\\n",
\t\t\t(long long)file->f_pos, f_flags,
\t\t\tmnt->mnt_id);
#else
\tseq_printf(m, "pos:\\t%lli\\nflags:\\t0%o\\nmnt_id:\\t%i\\n",
\t\t   (long long)file->f_pos, f_flags,
\t\t   real_mount(file->f_path.mnt)->mnt_id);

#endif"""
 new="""#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
    if (susfs_is_current_app_uid()) {
        struct inode *inode = file_inode(file);
        bool is_fuse = false;
        if (inode && susfs_is_inode_sus_kstat(inode, &is_fuse)) {
            int mnt_id = real_mount(file->f_path.mnt)->mnt_id;
            unsigned long ino = inode->i_ino;
            susfs_sus_kstat_spoof_proc_fd_seq_show(&mnt_id, &ino, inode->i_sb->s_dev);
            seq_printf(m, "pos:\\t%lli\\nflags:\\t0%o\\nmnt_id:\\t%i\\n",
                       (long long)file->f_pos, f_flags, mnt_id);
            goto out_fd_susfs;
        }
    }
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
    if (susfs_is_current_proc_umounted()) {
        struct mount *mnt = real_mount(file->f_path.mnt);
        if (mnt->mnt_id >= DEFAULT_KSU_MNT_ID) {
            seq_printf(m, "pos:\\t%lli\\nflags:\\t0%o\\nmnt_id:\\t%i\\n",
                       (long long)file->f_pos, f_flags,
                       susfs_get_non_sus_mnt_id_from_mnt(mnt));
            goto out_fd_susfs;
        }
    }
#endif
    seq_printf(m, "pos:\\t%lli\\nflags:\\t0%o\\nmnt_id:\\t%i\\n",
               (long long)file->f_pos, f_flags,
               real_mount(file->f_path.mnt)->mnt_id);
#if defined(CONFIG_KSU_SUSFS_SUS_MOUNT) || defined(CONFIG_KSU_SUSFS_SUS_KSTAT)
out_fd_susfs:
#endif"""
 s=one(s,old,new,"proc fd mount+KSTAT")
 return s

edit("fs/statfs.c",statfs)
edit("fs/proc/fd.c",proc_fd)
