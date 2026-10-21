#!/usr/bin/env python3
"""Reconcile SUSFS1.5-only entry points with SUSFS2.3's reboot/VFS API.

Do not synthesize empty implementations for undefined kernel symbols.
This intentionally removes deprecated hooks that have no SUSFS2.3 analogue.
The AVC log formatter retains context-spoof support using a readable context
comparison, avoiding missing external sid globals.
"""
from pathlib import Path
import re,sys
root=Path(sys.argv[1])
def patch(path, fn):
    p=root/path
    s=p.read_text()
    after=fn(s)
    if after==s:raise SystemExit(f"{path}: no changes made")
    p.write_text(after)
    print("SUSFS2.3 cleanup:",path)
def replace_one(s,before,after,path):
    cnt=s.count(before)
    if cnt!=1:raise SystemExit(f"{path}: expected 1 instance, got {cnt}: {before[:120]!r}")
    return s.replace(before,after,1)
def re_one(s,pat,rep,path):
    s,num=re.subn(pat,lambda m: rep,s,count=1,flags=re.DOTALL)
    if num!=1:raise SystemExit(f"{path}: expected regex once: {pat[:120]}")
    return s
def clean_prctl(s):
    path="kernel/sys.c"
    s=replace_one(s,"#ifdef CONFIG_KSU_SUSFS\nextern int susfs_handle_prctl(int option, unsigned long arg2, unsigned long arg3, unsigned long arg4, unsigned long arg5);\n#endif\n\n","",path)
    s=replace_one(s,"#ifdef CONFIG_KSU_SUSFS\n\tif (option == (int)0xDEADBEEF) {\n\t\treturn susfs_handle_prctl(option, arg2, arg3, arg4, arg5);\n\t}\n#endif\n\n","",path)
    return s
patch("kernel/sys.c",clean_prctl)
def clean_read(s):
    path="fs/read_write.c"
    s=re_one(s,r'#ifdef CONFIG_KSU_SUSFS\nextern struct static_key_true ksu_is_init_rc_hook_enabled;\n'
               r'extern __attribute__\(\(cold\)\) int ksu_handle_sys_read\(unsigned int fd, char __user \*\*buf_ptr,\s*'
               r'size_t \*count_ptr\);\n#endif\n\n',"",path)
    s=replace_one(s,"#ifdef CONFIG_KSU_SUSFS\n\tif (static_branch_unlikely(&ksu_is_init_rc_hook_enabled))\n\t\tksu_handle_sys_read(fd, NULL, NULL);\n#endif\n\n","",path)
    return s
patch("fs/read_write.c",clean_read)
def clean_namespace(s):
    path="fs/namespace.c"
    for macro,symbol in [
       ("CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT","susfs_auto_add_sus_ksu_default_mount"),
       ("CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT","susfs_auto_add_sus_bind_mount"),
       ("CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT","susfs_auto_add_try_umount_for_bind_mount")
    ]:
        pat=r'#ifdef '+macro+r'\nextern [^\n]*'+symbol+r'\([^\n]*\);\n'
        pat+=r'bool [^\n]* = true;\n#endif\n'
        s=re_one(s,pat,"",path)
    s=re_one(s,r'#if defined\(CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT\) \|\| defined\(CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT\)\n'
        r'.*?\n#endif // #if defined\(CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT\) \|\| defined\(CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT\)\n',
        "",path)
    s=re_one(s,r'#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT\n\s*// For both Legacy and Magic Mount KernelSU\n.*?\n#endif\n',
        "",path)
    s=re_one(s,r'#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT\nextern void susfs_try_umount_all\(uid_t uid\);\n'
        r'void susfs_run_try_umount_for_current_mnt_ns\(void\) \{.*?\n\}\n#endif\n(?=#ifdef CONFIG_KSU_SUSFS\nbool susfs_is_mnt_devname_ksu)',
        "",path)
    # SUSFS2.3 uses high mount IDs and mount helper queries. Old automatic
    # 1.5 unmount behavior is unsupported and must not silently linger.
    if any(term in s for term in ["susfs_auto_add_sus_ksu_default_mount",
                                 "susfs_auto_add_sus_bind_mount",
                                 "susfs_auto_add_try_umount_for_bind_mount",
                                 "susfs_try_umount_all"]):
        raise SystemExit("Namespace still contains SUSFS1.5 hooks")
    return s
patch("fs/namespace.c",clean_namespace)
def clean_avc(s):
    path="security/selinux/avc.c"
    s=replace_one(s,"extern u32 susfs_ksu_sid;\nextern u32 susfs_priv_app_sid;\n","",path)
    start="#ifdef CONFIG_KSU_SUSFS\n\tif (static_branch_likely(&susfs_is_avc_log_spoofing_enabled)) {"
    if s.count(start)!=1:raise SystemExit("SUSFS AVC spoof guard unexpected")
    s=re_one(s,
        r'#ifdef CONFIG_KSU_SUSFS\n\tif \(static_branch_likely\(&susfs_is_avc_log_spoofing_enabled\)\) \{'
        r'.*?\n\t\}\n#endif\n(?=\tif \(rc\))',
        '''#ifdef CONFIG_KSU_SUSFS
    if (static_branch_likely(&susfs_is_avc_log_spoofing_enabled) &&
        !rc && !strcmp(scontext, "u:r:ksu:s0")) {
        audit_log_format(ab, " tcontext=%s", "u:r:priv_app:s0:c512,c768");
        kfree(scontext);
        goto bypass_orig_flow;
    }
#endif
''',path)
    if "susfs_ksu_sid" in s or "susfs_priv_app_sid" in s:
        raise SystemExit("AVC still uses removed SUSFS sid globals")
    return s
patch("security/selinux/avc.c",clean_avc)
print("Removed obsolete SUSFS v1.5 link dependencies; modern interface retained")
