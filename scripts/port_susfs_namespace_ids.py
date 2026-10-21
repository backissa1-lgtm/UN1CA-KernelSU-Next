#!/usr/bin/env python3
"""Bridge UN1CA's Samsung mount-ID allocator onto SUSFS v2.3 ID ranges.

Samsung's RKP-protected clone/allocator implementation differs from the
generic Linux 4.9 SUSFS patch; preserve it during this compile iteration.
The old per-mount backup sentinel is kept private and namespaced.
This is an intermediate compatibility port, NOT full mount hiding validation.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
if s.count("DEFAULT_SUS_MNT_ID_FOR_KSU_PROC_UNSHARE") < 2:
    raise SystemExit("Existing Samsung unshare sentinel no longer present")
if "DEFAULT_SUS_MNT_GROUP_ID" not in s or "DEFAULT_SUS_MNT_ID" not in s:
    raise SystemExit("Legacy SUSFS1.5 mount ID allocator not recognized")
old="#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\nextern bool susfs_is_current_ksu_domain(void);"
if s.count(old)!=1: raise SystemExit("Samsung namespace header layout changed")
new="""#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
/* Local sentinel retained by Samsung's existing mount-id backup path.
 * It must never overlap legitimate allocated SUSFS v2.3 mount IDs. */
#define SUSFS_SAMSUNG_UNSHARE_ID_SENTINEL 1000000
extern bool susfs_is_current_ksu_domain(void);"""
s=s.replace(old,new,1)
s=s.replace("DEFAULT_SUS_MNT_ID_FOR_KSU_PROC_UNSHARE","SUSFS_SAMSUNG_UNSHARE_ID_SENTINEL")
s=s.replace("DEFAULT_SUS_MNT_GROUP_ID","DEFAULT_KSU_MNT_GROUP_ID")
s=s.replace("DEFAULT_SUS_MNT_ID","DEFAULT_KSU_MNT_ID")
for bad in ("DEFAULT_SUS_MNT_ID", "DEFAULT_SUS_MNT_GROUP_ID"):
    if bad in s:raise SystemExit(f"Legacy mount ID still referenced: {bad}")
if "DEFAULT_KSU_MNT_ID" not in s or "DEFAULT_KSU_MNT_GROUP_ID" not in s:
    raise SystemExit("Missing v2.3 allocation threshold")
p.write_text(s)
print("Migrated Samsung mount IDs to SUSFS2.3 high-ID thresholds; Samsung-specific clone logic retained for separate review")
