#!/usr/bin/env python3
"""Connect SUSFS 2.3 process-state flags to KSU Next's real setresuid handler.

KernelSU Next's upstream legacy tree handles app UID transitions in
hook/setuid_hook.c but does not set SUSFS TIF_PROC_UMOUNTED or
TIF_PROC_NO_SU. SUSFS2.3 VFS hooks require those flags.
Mirror the UID boundary already used by ksu_handle_umount:
isolated processes, or app UIDs with an enabled module-unmount policy.
Never mark manager / root users, preserve existing KSU root permissions.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1]);src=p.read_text()
inc='#include "compat/kernel_compat.h"'
if src.count(inc)!=1:raise SystemExit(f"Expected one KernelSU compatibility include, found {src.count(inc)}")
src=src.replace(inc,inc+'\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs_def.h>\n#endif',1)
old="""    // Handle kernel umount
    ksu_handle_umount(old_uid, new_uid);

    return 0;"""
new="""    // Handle kernel umount
    ksu_handle_umount(old_uid, new_uid);

#ifdef CONFIG_KSU_SUSFS
    /*
     * Keep SUSFS per-task view in step with the same KernelSU policy
     * that decides whether an app/isolated process gets modules unmounted.
     * A stale unmounted flag in a new privileged process would be wrong.
     */
    if (is_isolated_process(new_uid) ||
        (is_appuid(new_uid) && ksu_uid_should_umount(new_uid))) {
        susfs_set_current_proc_umounted();
        if (ksu_is_allow_uid_for_current(new_uid))
            susfs_clear_current_proc_no_su();
        else
            susfs_set_current_proc_no_su();
    } else {
        susfs_clear_current_proc_umounted();
        susfs_clear_current_proc_no_su();
    }
#endif

    return 0;"""
if src.count(old)!=1:raise SystemExit("Unexpected KernelSU Next setresuid/unmount implementation")
src=src.replace(old,new,1)
if src.count("susfs_set_current_proc_umounted();")!=1:raise SystemExit("Duplicate process-state setter")
p.write_text(src)
print("SUSFS2.3 per-task mount/SU flags now follow KernelSU Next's setresuid policy")
