#!/usr/bin/env python3
"""Connect SUSFS 2.3 reboot ABI to already boot-validated legacy KernelSU Next.

The Oct-17 legacy driver has its own reboot hook but does not dispatch
SUSFS_MAGIC. Enable the v2.3 commands for the official UAPI6 manager/ksud.
All callers must be root. Preserve original KernelSU su/manager handling.
"""
from pathlib import Path
import sys

if len(sys.argv)!=3:
    raise SystemExit("usage: wire_susfs23.py candidate/KernelSU-Next/kernel/supercall/supercall.c candidate/KernelSU-Next/kernel/core/init.c")
p=Path(sys.argv[1]);t=p.read_text()
h='#include <linux/utsname.h> // utsname() and uts_sem'
if t.count(h)!=1:raise SystemExit("Unexpected KSU supercall includes")
t=t.replace(h,h+'\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs.h>\n#endif',1)
marker='\t// Check if this is a request to install KSU fd'
if t.count(marker)!=1:raise SystemExit("KSU reboot dispatch marker not found")
cases="""#ifdef CONFIG_KSU_SUSFS
	/* SUSFS v2.3 uses the reboot supercall ABI, not the old prctl API. */
	if (magic2 == SUSFS_MAGIC) {
		if (current_uid().val != 0)
			return 0;
		switch (cmd) {
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
		case CMD_SUSFS_ADD_SUS_PATH: susfs_add_sus_path(arg); break;
		case CMD_SUSFS_ADD_SUS_PATH_LOOP: susfs_add_sus_path_loop(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
		case CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS:
			susfs_set_hide_sus_mnts_for_non_su_procs(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
		case CMD_SUSFS_ADD_SUS_KSTAT: susfs_add_sus_kstat(arg); break;
		case CMD_SUSFS_UPDATE_SUS_KSTAT: susfs_update_sus_kstat(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
		case CMD_SUSFS_SET_UNAME: susfs_set_uname(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
		case CMD_SUSFS_ENABLE_LOG: susfs_enable_log(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
		case CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG:
			susfs_set_cmdline_or_bootconfig(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
		case CMD_SUSFS_ADD_OPEN_REDIRECT: susfs_add_open_redirect(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MAP
		case CMD_SUSFS_ADD_SUS_MAP: susfs_add_sus_map(arg); break;
#endif
		case CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING:
			susfs_set_avc_log_spoofing(arg); break;
		case CMD_SUSFS_SHOW_VERSION: susfs_show_version(arg); break;
		case CMD_SUSFS_SHOW_VARIANT: susfs_show_variant(arg); break;
		case CMD_SUSFS_SHOW_ENABLED_FEATURES: susfs_get_enabled_features(arg); break;
		default: break;
		}
		return 0;
	}
#endif

"""
t=t.replace(marker,cases+marker,1)
p.write_text(t)

p=Path(sys.argv[2]);t=p.read_text()
target='#include "feature/adb_root.h"'
if t.count(target)!=1:raise SystemExit("KSU core init include mismatch")
t=t.replace(target,'#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs.h>\n#endif\n'+target,1)
target='\tksu_feature_init();'
if t.count(target)!=1:raise SystemExit("KSU init stage mismatch")
if 'susfs_init();' in t:raise SystemExit("SUSFS init already wired")
t=t.replace(target,target+'\n#ifdef CONFIG_KSU_SUSFS\n\tsusfs_init();\n#endif',1)
p.write_text(t)
print("KSU Next reboot dispatches SUSFS 2.3 commands; initializes SUSFS before runtime")
