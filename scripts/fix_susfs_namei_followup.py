#!/usr/bin/env python3
"""Resolve two kernel-4.9 patch placements that are invalid in Exynos 9810 namei.c.
 
The generic patch accidentally puts lookup_slow() logic inside sys_mknodat().
Its obsolete v1.5 OPEN_REDIRECT post-open logic also accesses removed inode
state flags. SUSFS2.3 implements redirect separately in fs/open.c.
"""
from pathlib import Path
import re, sys
p=Path(sys.argv[1]);s=p.read_text()

misplaced = (
    "#ifdef CONFIG_KSU_SUSFS_SUS_PATH\n"
    "\tif (is_nd_flags_lookup_last && !found_sus_path && dentry && !IS_ERR(dentry) && dentry->d_inode &&\n"
    "\t\tsusfs_is_inode_sus_path(dentry->d_inode))\n"
    "\t{\n"
    "\t\tif (d_in_lookup(dentry))\n"
    "\t\t\td_lookup_done(dentry);\n"
    "\t\tif (!(flags & LOOKUP_RCU))\n"
    "\t\t\tdput(dentry);\n"
    "\t\tdentry = d_alloc_parallel(dir, &susfs_fake_qstr_name, &wq);\n"
    "\t\tfound_sus_path = true;\n"
    "\t\tgoto retry;\n"
    "\t}\n"
    "#endif\n"
)
if s.count(misplaced)!=1:
    raise SystemExit(f"Expected one misplaced SUSFS block, got {s.count(misplaced)}")
s=s.replace(misplaced,"",1)

redirect_decl = "#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n\tstruct filename *fake_pathname;\n#endif\n"
if s.count(redirect_decl)!=1:
    raise SystemExit(f"Expected one legacy redirect declaration, got {s.count(redirect_decl)}")
s=s.replace(redirect_decl,"",1)
marker="\tif (!IS_ERR(filp) && unlikely(filp->f_inode->i_state & INODE_STATE_OPEN_REDIRECT)"
if s.count(marker)!=1:
    raise SystemExit("Expected exactly one v1.5 filp redirect hook")
regex=(r'#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n'
       r'\tif \(!IS_ERR\(filp\) && unlikely\(filp->f_inode->i_state & INODE_STATE_OPEN_REDIRECT\)'
       r'.*?\n#endif\n(?=\trestore_nameidata\(\);\n\treturn filp;)')
s,n=re.subn(regex,"",s,count=1,flags=re.DOTALL)
if n!=1:raise SystemExit("Old redirect hook boundary not found")
if "INODE_STATE_OPEN_REDIRECT" in s:
    raise SystemExit("Legacy OPEN_REDIRECT inode state still referenced")
p.write_text(s)
print("Dropped wrongly placed mknodat lookup code and obsolete namei redirect; SUSFS2.3 fs/open.c hook retained")
