#!/usr/bin/env python3
"""Audit obsolete SUSFS v1.5 kernel fields before lengthy compiler downloads.

This does NOT hide errors by globally defining compatibility fields.
"""
from pathlib import Path
import re,sys
if len(sys.argv)!=3:
    raise SystemExit("Usage: scan_stale_susfs.py candidate-kernel-dir output.txt")
root=Path(sys.argv[1]);output=Path(sys.argv[2])
rx=re.compile(r"\b(?:TASK_STRUCT_NON_ROOT_USER_APP_PROC|INODE_STATE_SUS_PATH|INODE_STATE_SUS_KSTAT|INODE_STATE_SUS_MOUNT|INODE_STATE_OPEN_REDIRECT|DEFAULT_SUS_MNT_ID|susfs_sus_ino_for_filldir64|susfs_sus_ino_for_generic_fillattr|susfs_sus_ino_for_show_map_vma)\b")
hits=[]
for section in ["fs","drivers","kernel","mm","security","include","KernelSU-Next"]:
    directory=root/section
    if not directory.is_dir():continue
    for path in directory.rglob("*"):
        if path.suffix not in (".c",".h"):continue
        # Analyze active lines, not commented-out source where possible.
        for lineno,line in enumerate(path.read_text(errors="replace").splitlines(),1):
            if rx.search(line) and not line.strip().startswith(("//","*","/*")):
                hits.append(f"{path.relative_to(root)}:{lineno}:{line.strip()}")
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text("\n".join(hits)+"\n" if hits else "No stale v1.5 SUSFS fields found.\n")
print(f"SUSFS v1.5 obsolete field references: {len(hits)}")
for hit in hits[:100]:print(hit)
if hits:raise SystemExit("Stale SUSFS1.5 fields require per-callsite v2.3 porting")
