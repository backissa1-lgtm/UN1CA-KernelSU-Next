#!/usr/bin/env bash
# Stage SUSFS v2.3 Linux 4.9 port atop independent boot-proven KSU Next worktree.
set -euo pipefail
kernel_dir="${1:?Usage: scripts/stage_susfs23.sh CANDIDATE_KERNEL_DIR}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$root/audit"
if [[ ! -d "$root/susfs/.git" ]]; then
  git clone --filter=blob:none --depth 1 --branch kernel-4.9-v2 \
    https://github.com/wxx9248/susfs4ksu.git "$root/susfs"
fi
git -C "$root/susfs" fetch --depth 1 origin 71345ded5af28f55d76ebcdc7a9df9cea56111e1
git -C "$root/susfs" checkout --detach 71345ded5af28f55d76ebcdc7a9df9cea56111e1
cp "$root/susfs/kernel_patches/fs/susfs.c" "$kernel_dir/fs/susfs.c"
cp "$root/susfs/kernel_patches/include/linux/susfs.h" "$kernel_dir/include/linux/susfs.h"
cp "$root/susfs/kernel_patches/include/linux/susfs_def.h" "$kernel_dir/include/linux/susfs_def.h"
set +e
(cd "$kernel_dir" && patch --batch --forward -p1 < "$root/susfs/kernel_patches/50_add_susfs_in_kernel-4.9.patch") > "$root/audit/susfs-patch-application.log" 2>&1
patch_status=$?
set -e
printf '%s\n' "$patch_status" > "$root/audit/susfs-original-patch-status.txt"
find "$kernel_dir" -name '*.rej' -print > "$root/audit/susfs-rejects.txt"
python3 - "$kernel_dir/fs/Makefile" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);rows=p.read_text().splitlines(keepends=True)
key="obj-$(CONFIG_KSU_SUSFS) += susfs.o"
out=[]; matched=0
for row in rows:
    if row.strip()==key:
        matched+=1
        if matched>1: continue
    out.append(row)
assert matched>=1,"SUSFS object entry missing"
p.write_text(''.join(out))
PY
python3 - "$kernel_dir/kernel/sys.c" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);t=p.read_text()
bad="#ifdef CONFIG_KSU_SUSFS\n\t(void)ksu_handle_setresuid(ruid, euid, suid);\n#endif\n\n"
assert t.count(bad)==1,"Incorrect setreuid hook occurrence changed"
p.write_text(t.replace(bad,"",1))
PY
python3 "$root/scripts/fix_susfs_open.py" "$kernel_dir/fs/open.c"
python3 "$root/scripts/fix_susfs_duplicate_hooks.py" "$kernel_dir"
python3 "$root/scripts/fix_susfs_stat_kstat.py" "$kernel_dir/fs/stat.c"
python3 "$root/scripts/fix_susfs_namei.py" "$kernel_dir/fs/namei.c"
git -C "$kernel_dir" add -N -- fs kernel mm security drivers include || true
git -C "$kernel_dir" diff --stat > "$root/audit/combined-susfs-stat.txt"
git -C "$kernel_dir" diff -- fs kernel mm security drivers include > "$root/audit/combined-susfs-port.patch"
echo 'Experimental combined port; not boot-validated.' > "$root/audit/NOT-YET-FLASHABLE.txt"
grep -E 'SUSFS_VERSION|SUSFS_VERSION_STR' "$kernel_dir/include/linux/susfs.h" "$kernel_dir/fs/susfs.c" | head -10 || true
