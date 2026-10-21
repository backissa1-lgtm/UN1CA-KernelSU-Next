#!/usr/bin/env python3
"""Drop obsolete SUSFS 1.5 hooks and implement SUSFS 2.3 AVC SID resolution.

No undefined functions are stubbed out. Old prctl protocol was replaced by
the SUSFS2.3 reboot supercall in scripts/wire_susfs23.py. Automatic mount
functions and init_rc callbacks belonged to the old port and do not exist
in upstream v2.3/KernelSU Next 33315. KernelSU Next's own unmount hook stays.
"""
from pathlib import Path
import re
import sys
root = Path(sys.argv[1])

def write(rel, action):
    p=root/rel
    old=p.read_text()
    new=action(old)
    if new==old:raise SystemExit(f"{rel}: no changes")
    p.write_text(new)
    print(f"Reconciled: {rel}")

def replace_exact(t,old,new,reason):
    n=t.count(old)
    if n!=1:raise SystemExit(f"{reason}: expected 1 matching block, got {n}")
    return t.replace(old,new,1)

def sys_prctl(s):
    before="#ifdef CONFIG_KSU_SUSFS\nextern int susfs_handle_prctl(int option, unsigned long arg2, unsigned long arg3, unsigned long arg4, unsigned long arg5);\n#endif\n\n"
    s=replace_exact(s,before,"","obsolete prctl declaration")
    before="#ifdef CONFIG_KSU_SUSFS\n\tif (option == (int)0xDEADBEEF) {\n\t\treturn susfs_handle_prctl(option, arg2, arg3, arg4, arg5);\n\t}\n#endif\n\n"
    return replace_exact(s,before,"","obsolete prctl interception")

def read_write(s):
    before="""#ifdef CONFIG_KSU_SUSFS
extern struct static_key_true ksu_is_init_rc_hook_enabled;
extern __attribute__((cold)) int ksu_handle_sys_read(unsigned int fd, char __user **buf_ptr,
            size_t *count_ptr);
#endif

"""
    if before not in s:
        # Different indentation found in generic upstream SUSFS patch.
        start=s.index("#ifdef CONFIG_KSU_SUSFS\nextern struct static_key_true ksu_is_init_rc_hook_enabled;")
        end=s.index("#endif\n",start)+len("#endif\n")
        s=s[:start]+s[end:]
    else:s=replace_exact(s,before,"","obsolete init rc declaration")
    before="#ifdef CONFIG_KSU_SUSFS\n\tif (static_branch_unlikely(&ksu_is_init_rc_hook_enabled))\n\t\tksu_handle_sys_read(fd, NULL, NULL);\n#endif\n\n"
    s=replace_exact(s,before,"","obsolete init rc invocation")
    assert "ksu_is_init_rc_hook_enabled" not in s
    return s

def stat(s):
    start=s.index("#ifdef CONFIG_KSU_SUSFS\nextern struct static_key_true ksu_is_init_rc_hook_enabled;")
    end=s.index("#endif\n",start)+len("#endif\n")
    s=s[:start]+s[end:]
    old="""#ifdef CONFIG_KSU_SUSFS
\t\tif (static_branch_unlikely(&ksu_is_init_rc_hook_enabled))
\t\t\tksu_handle_vfs_fstat(fd, &stat->size);
#endif
"""
    s=replace_exact(s,old,"","obsolete init rc fstat invocation")
    assert "ksu_is_init_rc_hook_enabled" not in s
    return s

def namespace(s):
    blocks=[
       r'#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT\n.*?\n#endif\n',
       r'#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT\n.*?\n#endif\n',
       r'#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT\n.*?\n#endif\n',
       r'#if defined\(CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT\) \|\| defined\(CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT\)\n.*?\n#endif // #if defined\(CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT\) \|\| defined\(CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT\)\n',
    ]
    for i,pat in enumerate(blocks):
        s,n=re.subn(pat,"",s,count=1,flags=re.DOTALL)
        if n!=1:raise SystemExit(f"namespace automatic mount removal {i}: {n}")
    # Legacy v1.5 automatic registration following do_mount() was removed
    # from 2.3; root-mode KernelSU can still register SUSFS mount rules by
    # its explicit reboot ioctl handler (no pretend fallback).
    pat=r'#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT\n\t// For both Legacy and Magic Mount KernelSU\n.*?\n#endif\n'
    s,n=re.subn(pat,"",s,count=1,flags=re.DOTALL)
    if n!=1:raise SystemExit(f"Legacy default mount auto-add call count {n}")
    # The old function (including umount-all) no longer exists in SUSFS2.3;
    # modern KernelSU uses its own kernel_umount support.
    pat=r'#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT\nextern void susfs_try_umount_all\(uid_t uid\);\nvoid susfs_run_try_umount_for_current_mnt_ns\(void\) \{.*?\n\}\n#endif\n'
    s,n=re.subn(pat,"",s,count=1,flags=re.DOTALL)
    if n!=1:raise SystemExit(f"Legacy umount-all removal count {n}")
    for sym in ("susfs_auto_add_sus_ksu_default_mount","susfs_auto_add_sus_bind_mount",
                "susfs_auto_add_try_umount_for_bind_mount","susfs_try_umount_all"):
        if sym in s:raise SystemExit("Unported legacy symbol remains "+sym)
    return s

def susfs(s):
    old="/* susfs avc log spoofing */\nDEFINE_STATIC_KEY_FALSE(susfs_is_avc_log_spoofing_enabled);"
    new="""/* SUSFS 2.3 AVC spoofing SIDs are resolved from the ACTIVE SELinux policy
 * when the feature is enabled, not hardcoded across ROM builds. */
u32 susfs_ksu_sid;
u32 susfs_priv_app_sid;
/* susfs avc log spoofing */
DEFINE_STATIC_KEY_FALSE(susfs_is_avc_log_spoofing_enabled);"""
    s=replace_exact(s,old,new,"AVC SID globals")
    old="""\tif (info.enabled) {
\t\tstatic_branch_enable(&susfs_is_avc_log_spoofing_enabled);
\t\tSUSFS_LOGI("enabling susfs_avc_log_spoofing\\n");
\t} else {"""
    new="""\tif (info.enabled) {
\t\tconst char ksu_context[] = "u:r:ksu:s0";
\t\tconst char priv_context[] = "u:r:priv_app:s0:c512,c768";
\t\t/* Called after policy load, by the privileged SUSFS ioctl. */
\t\tif (security_secctx_to_secid(ksu_context, sizeof(ksu_context)-1,
\t\t\t\t\t &susfs_ksu_sid) ||
\t\t    security_secctx_to_secid(priv_context, sizeof(priv_context)-1,
\t\t\t\t\t &susfs_priv_app_sid)) {
\t\t\tinfo.err = -EINVAL;
\t\t\tgoto out_copy_to_user;
\t\t}
\t\tstatic_branch_enable(&susfs_is_avc_log_spoofing_enabled);
\t\tSUSFS_LOGI("enabling susfs_avc_log_spoofing\\n");
\t} else {"""
    return replace_exact(s,old,new,"AVC SID activation")

def avc(s):
    # Upstream kernel patch skipped cleanup when replacing tcontext. Fix the
    # allocated SELinux context before taking the spoofed branch.
    old='''\t\t\telse
\t\t\t\taudit_log_format(ab, " tcontext=%s", "u:r:priv_app:s0:c512,c768");
\t\t\tgoto bypass_orig_flow;'''
    new='''\t\t\telse {
\t\t\t\taudit_log_format(ab, " tcontext=%s", "u:r:priv_app:s0:c512,c768");
\t\t\t\tkfree(scontext);
\t\t\t}
\t\t\tgoto bypass_orig_flow;'''
    return replace_exact(s,old,new,"AVC context cleanup")

write("kernel/sys.c",sys_prctl)
write("fs/read_write.c",read_write)
write("fs/stat.c",stat)
write("fs/namespace.c",namespace)
write("fs/susfs.c",susfs)
write("security/selinux/avc.c",avc)
