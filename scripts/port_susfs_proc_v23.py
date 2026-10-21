#!/usr/bin/env python3
"""Reconcile VFS /proc hooks retained from SUSFS 1.5.5 with SUSFS 2.3.

This script makes targeted, asserted conversions; it does NOT silence or
globally alias obsolete fields. Mount namespace implementation is separate.
"""
from pathlib import Path
import re,sys
root=Path(sys.argv[1])

def load(path):return (root/path).read_text()
def save(path,s): (root/path).write_text(s)
def replace_once(s,old,new,label):
    if s.count(old)!=1:raise SystemExit(f"{label}: expected one occurrence, found {s.count(old)}")
    return s.replace(old,new,1)

# Directory listing: new v2.3 ilookup path filter is already staged and
# replaces both old 1.5 callbacks. Drop only the dead extern.
path="fs/readdir.c";s=load(path)
old="#ifdef CONFIG_KSU_SUSFS_SUS_PATH\nextern int susfs_sus_ino_for_filldir64(unsigned long ino);\n#endif\n"
s=replace_once(s,old,"",path)
if s.count("susfs_is_inode_sus_path(")<2:
    raise SystemExit("readdir: missing both v2.3 inode filters")
save(path,s)

# The generic v2.3 patch already provides susfs_show_vfsmnt, susfs_show_mountinfo,
# and susfs_show_vfsstat wrappers selected only when hiding is enabled.
# Old unconditional mount ID exclusions in the ordinary show_* methods are
# redundant and would hide otherwise visible mounts even with hiding off.
path="fs/proc_namespace.c";s=load(path)
old="#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n\tif (unlikely(r->mnt_id >= DEFAULT_SUS_MNT_ID))\n\t\treturn 0;\n#endif\n"
if s.count(old)!=3:raise SystemExit(f"{path}: expected three old checks; found {s.count(old)}")
if "susfs_show_vfsmnt" not in s or "susfs_show_mountinfo" not in s or "susfs_show_vfsstat" not in s:
    raise SystemExit(f"{path}: modern v2.3 wrappers missing")
s=s.replace(old,"")
save(path,s)

# /proc/pid/maps: replace old inode state / v1 spoof helper with v2.3
# inode-based spoofing after computing dev and ino. Ported SUS_MAP/redirect
# hooks are tracked separately as patch rejections.
path="fs/proc/task_mmu.c";s=load(path)
old="#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\nextern void susfs_sus_ino_for_show_map_vma(unsigned long ino, dev_t *out_dev, unsigned long *out_ino);\n#endif"
new="#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\nextern void susfs_sus_kstat_spoof_show_map_vma(struct inode *inode, dev_t *out_dev,\n\t\t\tunsigned long *out_ino);\n#endif"
s=replace_once(s,old,new,path+" prototype")
old="""#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
\t\tif (unlikely(inode->i_state & INODE_STATE_SUS_KSTAT)) {
\t\t\tsusfs_sus_ino_for_show_map_vma(inode->i_ino, &dev, &ino);
\t\t\tgoto bypass_orig_flow;
\t\t}
#endif
\t\tdev = inode->i_sb->s_dev;
\t\tino = inode->i_ino;
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
bypass_orig_flow:
#endif"""
new="""\t\tdev = inode->i_sb->s_dev;
\t\tino = inode->i_ino;
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
\t\tif (susfs_is_current_app_uid())
\t\t\tsusfs_sus_kstat_spoof_show_map_vma(inode, &dev, &ino);
#endif"""
s=replace_once(s,old,new,path+" vma hook")
save(path,s)
print("Ported readdir + 3 /proc mount listing hooks + /proc maps KSTAT to SUSFS2.3")
