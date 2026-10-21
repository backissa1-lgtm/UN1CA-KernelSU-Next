#!/usr/bin/env python3
"""Restore original UN1CA SUSFS 1.5.5 integration bridges to updated KSU Next.

Copy functions verbatim from pinned Eend15 kernel instead of inventing no-op
substitutes for previously functional SELinux, unmount, devpts and sus_su hooks.
The source root is the EXACT same pinned baseline used for this candidate.
"""
from pathlib import Path
import sys
if len(sys.argv) != 3:
    raise SystemExit("Usage: restore_susfs_bridges.py ORIGINAL_KSU_KERNEL CANDIDATE_KSU_KERNEL")
old_root, new_root = map(Path, sys.argv[1:])

def original_segment(path, begin, end):
    text = (old_root / path).read_text()
    if text.count(begin) != 1:
        raise SystemExit(f"{path}: cannot uniquely locate original bridge start")
    start = text.index(begin)
    tail = text[start:]
    if end not in tail:
        raise SystemExit(f"{path}: cannot find original bridge end")
    return tail[:tail.index(end) + len(end)]

def append_bridge(path, marker, end):
    chunk = original_segment(path, marker, end)
    destination = new_root / path
    text = destination.read_text()
    # Never duplicate bridges; apply only on newer driver that lacks them.
    if marker in text:
        raise SystemExit(f"{path}: target already defines {marker!r}")
    destination.write_text(text.rstrip() + "\n\n" + chunk.rstrip() + "\n")
    print(f"Restored original {path} bridge ({len(chunk)} bytes)")

append_bridge(
    "selinux/selinux.c",
    "#ifdef CONFIG_KSU_SUSFS\nbool susfs_is_current_ksu_domain(void)",
    "void susfs_set_zygote_sid(void) {}\n#endif",
)
append_bridge(
    "policy/app_profile.c",
    "#ifdef CONFIG_KSU_SUSFS_SUS_SU\nvoid ksu_escape_to_root(void)",
    "void ksu_susfs_disable_sus_su(void) {}\n#endif",
)
append_bridge(
    "feature/kernel_umount.c",
    "#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT\nvoid ksu_try_umount(",
    "\n#endif",
)

old = (old_root / "feature/sucompat.c").read_text()
start_marker = "int __ksu_handle_devpts(struct inode *inode)"
stop_marker = "// sucompat: permitted process can execute 'su' to gain root access."
if old.count(start_marker) != 1 or old.count(stop_marker) != 1:
    raise SystemExit("Original devpts bridge markers missing")
part = old[old.index(start_marker):old.index(stop_marker)]
dst = new_root / "feature/sucompat.c"
text = dst.read_text()
if "__ksu_handle_devpts(" in text or "ksu_handle_devpts(" in text:
    raise SystemExit("Modern source already defines devpts bridge")
if text.count(stop_marker) != 1:
    raise SystemExit("New sucompat insertion point not unique")
dst.write_text(text.replace(stop_marker,part.rstrip() + "\n\n" + stop_marker,1))
print("Restored original UN1CA devpts hook logic")
