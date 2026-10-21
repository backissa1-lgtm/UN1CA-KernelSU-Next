#!/usr/bin/env python3
"""Remove the obsolete v1.5.5 readdir hide callbacks.

SUSFS v2.3 kernel-4.9 patch adds its own ilookup()/susfs_is_inode_sus_path
filter in filldir() and filldir64(). Keep that new code, remove the two
legacy callbacks referencing task state fields removed in v2.3.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
old=("#ifdef CONFIG_KSU_SUSFS_SUS_PATH\n"
     "\tif (likely(current->susfs_task_state & TASK_STRUCT_NON_ROOT_USER_APP_PROC) && susfs_sus_ino_for_filldir64(ino)) {\n"
     "\t\treturn 0;\n"
     "\t}\n"
     "#endif\n")
if s.count(old)!=2: raise SystemExit(f"Expected two old readdir callbacks, found {s.count(old)}")
s=s.replace(old,"")
if s.count("susfs_is_inode_sus_path(inode)")<2:
    raise SystemExit("Missing newer SUSFS2.3 readdir implementation")
p.write_text(s)
print("Replaced both 1.5.5 readdir checks with ported SUSFS 2.3 inode filter")
