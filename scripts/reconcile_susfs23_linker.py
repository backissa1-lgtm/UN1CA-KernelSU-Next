#!/usr/bin/env python3
"""Reconcile superseded SUSFS v1.5 ABI callbacks with SUSFS 2.3.

The new SUSFS ABI uses reboot(SUSFS_MAGIC) rather than prctl(0xDEADBEEF).
Automatic 1.5 mount registration and try_umount functions were removed in
2.3; preserve newer mount-ID and per-process hiding hooks instead.
Old ReSukiSU read/init-rc hook is not implemented by the pinned KSU Next
driver (which has its own boot/runtime hooks). AVC spoofing uses the actual
SELinux target context to avoid undefined obsolete numeric SID globals.
The code is guarded by exact patterns: abort instead of silently changing
unrecognized Samsung source.
"""
from pathlib import Path
import re
import sys
root=Path(sys.argv[1])
def change(path, transform):
    p=root/path
    original=p.read_text()
    changed=transform(original)
    if changed==original: raise SystemExit(f"{path}: no changes made")
    p.write_text(changed)
    print(f"Reconciled: {path}")
def one(s,old,new,label):
    count=s.count(old)
    if count!=1: raise SystemExit(f"{label}: expected one match, got {count}")
    return s.replace(old,new,1)
def rematch(s,pattern,replace,label):
    s,count=re.subn(pattern,lambda m:replace,s,count=1,flags=re.DOTALL)
    if count!=1:raise SystemExit(f"{label}: expected one regex match, got {count}")
    return s

def sys_prctl(s):
    old="""#ifdef CONFIG_KSU_SUSFS
extern int susfs_handle_prctl(int option, unsigned long arg2, unsigned long arg3, unsigned long arg4, unsigned long arg5);
#endif
"""
    s=one(s,old,"","kernel/sys.c obsolete prctl declaration")
    old="""#ifdef CONFIG_KSU_SUSFS
\tif (option == (int)0xDEADBEEF) {
\t\treturn susfs_handle_prctl(option, arg2, arg3, arg4, arg5);
\t}
#endif
"""
    s=one(s,old,"","kernel/sys.c prctl callback")
    return s

def read_write(s):
    s=rematch(s,r'\n#ifdef CONFIG_KSU_SUSFS\nextern struct static_key_true ksu_is_init_rc_hook_enabled;\n'
      r'extern __attribute__\(\(cold\)\) int ksu_handle_sys_read\([^;]+;\n#endif\n',
      "\n","fs/read_write.c unsupported ReSukiSU init-rc prototype")
    old="""#ifdef CONFIG_KSU_SUSFS
\tif (static_branch_unlikely(&ksu_is_init_rc_hook_enabled))
\t\tksu_handle_sys_read(fd, NULL, NULL);
#endif
"""
    s=one(s,old,"","fs/read_write.c unsupported read syscall hook")
    return s

def namespace(s):
    olddecls=[
"""#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT
extern void susfs_auto_add_sus_ksu_default_mount(const char __user *to_pathname);
bool susfs_is_auto_add_sus_ksu_default_mount_enabled = true;
#endif
""",
"""#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT
extern int susfs_auto_add_sus_bind_mount(const char *pathname, struct path *path_target);
bool susfs_is_auto_add_sus_bind_mount_enabled = true;
#endif
""",
"""#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT
extern void susfs_auto_add_try_umount_for_bind_mount(struct path *path);
bool susfs_is_auto_add_try_umount_for_bind_mount_enabled = true;
#endif
"""]
    for i,decl in enumerate(olddecls):
        s=one(s,decl,"",f"namespace obsolete declaration {i+1}")
    p=r'\n#if defined\(CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT\) \|\| defined\(CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT\)\n\t// Check if bind mounted path.*?\n#endif // #if defined\(CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT\) \|\| defined\(CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT\)\n'
    s=rematch(s,p,"\n","namespace removed bind-mount post-hook")
    p=r'\n#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT\n\t// For both Legacy and Magic Mount KernelSU.*?\n#endif\n(?=dput_out:)'
    s=rematch(s,p,"\n","namespace removed default-mount post-hook")
    p=r'\n#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT\nextern void susfs_try_umount_all\(uid_t uid\);\nvoid susfs_run_try_umount_for_current_mnt_ns\(void\) \{.*?\n\}\n#endif\n(?=#ifdef CONFIG_KSU_SUSFS)'
    s=rematch(s,p,"\n","namespace removed old v1.5 try_umount entry")
    for sym in ("susfs_auto_add_sus_ksu_default_mount","susfs_auto_add_sus_bind_mount",
                "susfs_auto_add_try_umount_for_bind_mount","susfs_try_umount_all"):
        if sym in s:raise SystemExit(f"namespace still calls obsolete {sym}")
    if "susfs_get_non_sus_vfsmnt_from_vfsmnt(" not in s:
        raise SystemExit("namespace: newer 2.3 mount lookup helpers were lost")
    return s

def avc(s):
    s=one(s,"extern u32 susfs_ksu_sid;\nextern u32 susfs_priv_app_sid;\n","",
      "AVC obsolete numeric SID declarations")
    pat=r'\n#ifdef CONFIG_KSU_SUSFS\n\tif \(static_branch_likely\(&susfs_is_avc_log_spoofing_enabled\)\) \{.*?\n\t\}\n#endif\n(?=\tif \(rc\)\n\t\taudit_log_format\(ab, " tsid=%d", tsid\);)'
    s=rematch(s,pat,"\n","AVC obsolete SID conditional")
    old="""\tif (rc)
\t\taudit_log_format(ab, " tsid=%d", tsid);
\telse {
\t\taudit_log_format(ab, " tcontext=%s", scontext);
\t\tkfree(scontext);
\t}
#ifdef CONFIG_KSU_SUSFS
bypass_orig_flow:
#endif
"""
    new="""\tif (rc)
\t\taudit_log_format(ab, " tsid=%d", tsid);
\telse {
#ifdef CONFIG_KSU_SUSFS
\t\tif (static_branch_unlikely(&susfs_is_avc_log_spoofing_enabled) &&
\t\t    scontext_len >= sizeof("u:r:ksu:s0") - 1 &&
\t\t    !memcmp(scontext, "u:r:ksu:s0", sizeof("u:r:ksu:s0") - 1))
\t\t\taudit_log_format(ab, " tcontext=%s", "u:r:priv_app:s0:c512,c768");
\t\telse
#endif
\t\t\taudit_log_format(ab, " tcontext=%s", scontext);
\t\tkfree(scontext);
\t}
"""
    s=one(s,old,new,"AVC integrate context-aware spoof, preserve kfree")
    if "susfs_ksu_sid" in s or "susfs_priv_app_sid" in s:raise SystemExit("AVC SID references remain")
    return s

change("kernel/sys.c",sys_prctl)
change("fs/read_write.c",read_write)
change("fs/namespace.c",namespace)
change("security/selinux/avc.c",avc)
print("SUSFS2.3 old ABI bridging completed; mount behavior still requires physical validation")
