#!/usr/bin/env python3
"""Add SUSFS2.3 non-hidden mount lookup functions to Samsung Exynos 9810 VFS.

Unlike generic Linux 4.9, the Samsung source uses DEFINE_SEQLOCK(mount_lock)
and can build with CONFIG_RKP_NS_PROT (mnt->mnt is a pointer). Protect
the mount-parent walk under its existing exclusive reader seqlock and get
references before releasing it. No generic write-side mount-lock function
is assumed to exist.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
if "DEFINE_SEQLOCK(mount_lock)" not in s or "read_seqlock_excl(&mount_lock)" not in s:
    raise SystemExit("Not Samsung mount_lock implementation")
if "susfs_get_non_sus_mnt_id_from_mnt" in s or "susfs_get_non_sus_vfsmnt_from_vfsmnt" in s:
    raise SystemExit("Mount lookup helpers already present")
target="};\n\n#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT\nextern void susfs_try_umount_all"
if s.count(target)!=1:
    raise SystemExit("mntns_operations insertion point changed")
chunk="""};

#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
/*
 * SUSFS 2.3 mount-ID and vfsmount lookup adapted to Samsung's
 * mount_lock seqlock and CONFIG_RKP_NS_PROT vfsmount representation.
 */
int susfs_get_non_sus_mnt_id_from_mnt(struct mount *orig_mnt)
{
    struct mount *mnt = orig_mnt;
    int ret = 0;
    read_seqlock_excl(&mount_lock);
    while (mnt && mnt->mnt_parent && mnt != mnt->mnt_parent &&
           mnt->mnt_id >= DEFAULT_KSU_MNT_ID)
        mnt = mnt->mnt_parent;
    if (mnt)
        ret = mnt->mnt_id;
    read_sequnlock_excl(&mount_lock);
    return ret;
}

struct vfsmount *susfs_get_non_sus_vfsmnt_from_vfsmnt(struct vfsmount *vfsmnt)
{
    struct mount *mnt = real_mount(vfsmnt);
    struct vfsmount *legit = NULL;
    read_seqlock_excl(&mount_lock);
    while (mnt && mnt->mnt_parent && mnt != mnt->mnt_parent &&
           mnt->mnt_id >= DEFAULT_KSU_MNT_ID)
        mnt = mnt->mnt_parent;
    if (mnt) {
#ifdef CONFIG_RKP_NS_PROT
        legit = mnt->mnt;
#else
        legit = &mnt->mnt;
#endif
        mntget(legit);
        dget(legit->mnt_root);
    }
    read_sequnlock_excl(&mount_lock);
    return legit;
}
#endif

#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
extern void susfs_try_umount_all"""
s=s.replace(target,chunk,1)
p.write_text(s)
print("Added Samsung-aware SUSFS2.3 mount lookup helpers under mount_lock")
