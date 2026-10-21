#!/usr/bin/env python3
"""Replace old SUSFS 1.5 /proc/cmdline hook with SUSFS 2.3 static-key ABI.

Old susfs_spoof_cmdline_or_bootconfig returns int in Eend15 and is tested
with !return_value. SUSFS 2.3 returns void, so retaining that check invokes
undefined behavior. Preserve Samsung's existing new_command_line fallback.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
old='#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG\nextern int susfs_spoof_cmdline_or_bootconfig(struct seq_file *m);\n#endif'
new='#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG\n#include <linux/jump_label.h>\nextern struct static_key_false susfs_is_fake_cmdline_or_bootconfig_buffer_set;\nextern void susfs_spoof_cmdline_or_bootconfig(struct seq_file *m);\n#endif'
if s.count(old)!=1:raise SystemExit('Legacy /proc/cmdline SUSFS declaration missing')
s=s.replace(old,new,1)
old="""#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
\tif (!susfs_spoof_cmdline_or_bootconfig(m)) {
\t\tseq_putc(m, '\\n');
\t\treturn 0;
\t}
#endif"""
new="""#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
\tif (static_branch_unlikely(&susfs_is_fake_cmdline_or_bootconfig_buffer_set)) {
\t\tsusfs_spoof_cmdline_or_bootconfig(m);
\t\tseq_putc(m, '\\n');
\t\treturn 0;
\t}
#endif"""
if s.count(old)!=1:raise SystemExit('Old /proc/cmdline SUSFS return check changed')
s=s.replace(old,new,1)
if "seq_puts(m, new_command_line);" not in s: raise SystemExit('Missing Samsung command line fallback')
p.write_text(s)
print('SUSFS2.3 /proc/cmdline static-key ABI safely integrated, Samsung fallback retained')
