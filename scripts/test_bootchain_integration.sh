#!/usr/bin/env bash
set -euo pipefail
bash -n bootchain/apply.sh bootchain/recovery-stage.sh bootchain/first-boot.sh
# Ensure the exact release set is pinned and passes manifest schema checks.
test "$(grep -cv '^#' bootchain/assets.manifest)" -eq 5
while read -r name digest url; do
  case "$name" in ''|\#*) continue;; esac
  if [ "$name" = busybox-aarch64 ]; then
    [[ "$digest" =~ ^[a-f0-9]{40}$ ]]
  else
    [[ "$digest" =~ ^[a-f0-9]{64}$ ]]
  fi
  [[ "$url" == https://github.com/*/releases/download/* || "$url" == https://raw.githubusercontent.com/* || "$url" == https://github.com/KernelSU-Next/KernelSU-Next/actions/runs/39297115788 ]]
done < bootchain/assets.manifest
python3 -m py_compile scripts/inject_bootchain_hook.py
python3 -m py_compile scripts/fix_ksu_allowlist_persistence.py scripts/fix_ksu_throne_tracker_reads.py
allowlist_test="$(mktemp)"
trap 'rm -f "$allowlist_test"' EXIT
cat > "$allowlist_test" <<'EOS'
#include "compat/kernel_compat.h"
static int demo(void) {
  if (kernel_read(fp, &magic, sizeof(magic), &off) != sizeof(magic))
    return -1;
  if (kernel_read(fp, &version, sizeof(version), &off) != sizeof(version))
    return -1;
  ret = kernel_read(fp, &profile, app_profile_size, &off);
  return ret;
}
EOS
python3 scripts/fix_ksu_allowlist_persistence.py "$allowlist_test"
python3 scripts/fix_ksu_allowlist_persistence.py --verify "$allowlist_test"
! grep -Eq '(^|[^a-zA-Z_])kernel_read\(fp, &' "$allowlist_test"
rm -f "$allowlist_test"

tracker_test="$(mktemp)"
cat > "$tracker_test" <<'EOS'
#include "ksu.h"
ssize_t demo(void) {
  ssize_t count = kernel_read(fp, &chr, sizeof(chr), &pos);
  count = kernel_read(fp, buf, sizeof(buf) - 1, &line_start);
  return count;
}
EOS
python3 scripts/fix_ksu_throne_tracker_reads.py "$tracker_test"
python3 scripts/fix_ksu_throne_tracker_reads.py --verify "$tracker_test"
grep -Fq '#include "compat/kernel_compat.h"' "$tracker_test"
test "$(grep -c 'ksu_kernel_read_compat(' "$tracker_test")" -eq 2
! grep -Eq '(^|[^a-zA-Z_])kernel_read\(fp,' "$tracker_test"
rm -f "$tracker_test"

# Re-flashing cannot skip the one-time module service because of old setup.done.
grep -Fq 'touch "$STAGE/setup.pending"' bootchain/recovery-stage.sh
grep -Fq 'rm -f "$STAGE/setup.done"' bootchain/recovery-stage.sh
grep -Fq 'rm -f "$MOD/disable" "$MOD/remove"' bootchain/recovery-stage.sh
grep -Fq '[ -f "$STAGE/setup.pending" ] || exit 0' bootchain/recovery-stage.sh
grep -Fq '[ -f "$PENDING" ] || exit 0' bootchain/first-boot.sh
grep -Fq 'rm -f "$PENDING" || fail' bootchain/first-boot.sh
python3 - <<'PY'
from pathlib import Path
stage = Path("bootchain/recovery-stage.sh").read_text()
first = Path("bootchain/first-boot.sh").read_text()
assert stage.index('touch "$STAGE/setup.pending"') > stage.index('touch "$MOD/skip_mount"')
assert stage.index('rm -f "$STAGE/setup.done"') > stage.index('touch "$STAGE/setup.pending"')
assert first.index('touch "$DONE"') < first.index('rm -f "$PENDING"') < first.index('if ! reboot;')
assert '[ -f "$DONE" ] && exit 0' not in first
PY


tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/update-binary" <<'EOS'
#!/system/bin/sh
device=G965F
if echo $device | grep 'G965F'; then
    echo "Kernel installed"
fi
EOS
python3 scripts/inject_bootchain_hook.py "$tmp/update-binary"
bash -n "$tmp/update-binary"
grep -q G965F_BOOTCHAIN_INTEGRATION_V1 "$tmp/update-binary"

# Hook insertion is fail-closed if repeated or on an unexpected installer.
if python3 scripts/inject_bootchain_hook.py "$tmp/update-binary"; then
  echo "Duplicate hook unexpectedly accepted" >&2
  exit 1
fi
cat > "$tmp/not-our-installer" <<'EOS'
#!/system/bin/sh
echo "Unexpected installer"
EOS
if python3 scripts/inject_bootchain_hook.py "$tmp/not-our-installer"; then
  echo "Unexpected installer layout accepted" >&2
  exit 1
fi

# The original installer exit code must remain unchanged on failure.
sed -i 's/echo "Kernel installed"/exit 19/' "$tmp/update-binary"
if sh "$tmp/update-binary" unused unused /tmp/fake.zip; then
  echo "Installer failure was masked by boot-chain hook" >&2
  exit 1
else
  test "$?" -eq 19
fi
echo "Boot-chain script and installer hook validation passed"
