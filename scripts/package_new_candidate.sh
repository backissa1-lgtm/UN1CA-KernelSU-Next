#!/usr/bin/env bash
# Rebase G965F kernel against verified derivative of UN1CA installer; preserve tested DTB.
set -euo pipefail
if [[ "$#" != 3 ]]; then
  echo "usage: $0 verified-template.zip candidate-boot.img output.zip" >&2
  exit 2
fi
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
template="$(realpath "$1")"
image="$(realpath "$2")"
output="$(realpath -m "$3")"
template_sha="3c10792029483d354e8b2e9072379cd0a9af653b003f3f319530d6852a8d0a2f"
original_sha="3e405a08fd5e0b4f8492096be9003349bb8372e4f16ec43f0308095d6615203f"
echo "$template_sha  $template" | sha256sum -c -
for cmd in bsdiff bspatch unzip zip python3; do command -v "$cmd" >/dev/null; done
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/repack"
unzip -q "$template" -d "$tmp/repack"
test -s "$tmp/repack/floyd/G960F-kernel"
test -s "$tmp/repack/floyd/G965F-kernel"
test -s "$tmp/repack/floyd/G960F-dtb"
test -s "$tmp/repack/floyd/G965F-dtb"
# Carry the tested root/zygisk/vector startup repairs with the kernel ZIP.
# The existing recovery installer is left intact except for a G965F-only
# success hook, which runs the helper only if decrypted /data is accessible.
install -D -m 0755 "$root/bootchain/apply.sh" "$tmp/repack/bootchain/apply.sh"
python3 "$root/scripts/inject_bootchain_hook.py" \
  "$tmp/repack/META-INF/com/google/android/update-binary"
grep -q 'G965F_BOOTCHAIN_INTEGRATION_V1' "$tmp/repack/META-INF/com/google/android/update-binary"
python3 "$root/scripts/extract_android_boot_v0.py" \
  "$image" "$tmp/kernel" "$tmp/candidate-dtb" > "$tmp/kernel-metadata.json"

# Replace only G965F kernel delta and prove it reconstructs the new kernel exactly.
bsdiff "$tmp/repack/floyd/G960F-kernel" "$tmp/kernel" "$tmp/repack/floyd/G965F-kernel"
bspatch "$tmp/repack/floyd/G960F-kernel" "$tmp/test-kernel" "$tmp/repack/floyd/G965F-kernel"
cmp "$tmp/kernel" "$tmp/test-kernel"
bspatch "$tmp/repack/floyd/G960F-dtb" "$tmp/original-G965F-dtb" "$tmp/repack/floyd/G965F-dtb"
test -s "$tmp/original-G965F-dtb"

python3 - "$tmp/repack/META-INF/com/google/android/update-binary" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text(errors="replace")
assert s.count("if echo $device | grep 'G965F'; then")==1, "Expected G965F-only installer"
assert "if echo $device | grep '[GN]96[05][FN]'; then" not in s
PY

cat > "$tmp/repack/BUILD-NOTES.txt" <<EOF
EXPERIMENTAL G965F KERNEL. NOT BOOT-TESTED ON DEVICE.
SM-G965F/star2lte, UN1CA Android 16, EROFS, Enforcing; SUSFS v1.5.5 preserved.
UN1CA source installer SHA256: $original_sha
Verified derivative ZIP SHA256: $template_sha
Only G965F-kernel patch changed; original G965F DTB retained.
Installer preserves current phone ramdisk.
SELinux Enforcing retained. Linux 4.9 init -> u:r:ksu:s0 bounded-exec exception corrected.
G965F boot-chain post-flash helper included: bootchain/apply.sh.
On successful recovery flash, it runs automatically ONLY if /data/adb/modules
is accessible (recovery has decrypted /data). Otherwise run after first boot:
  su -c 'sh /path/to/extracted/bootchain/apply.sh'
The helper preserves the verified UAPI 6 /data/adb/ksud, protects it using
F2FS immutable (remove before future KernelSU userspace upgrades), patches
NeoZygisk post-fs-data.sh against repeated monitor/socket destruction, and
patches Vector service.sh to use BusyBox unshare without force-restarting
system_server. Every edited module script gets a backup, and the helper
is idempotent. It does NOT bundle a ksud binary or create /metadata mounts.
If UAPI 6 ksud is absent, install a compatible manager/daemon first.
Only the kernel itself is known to have booted on the target. The newly
integrated recovery hook is not yet flash-tested. Inspect installation logs.
Candidate boot image SHA256: $(sha256sum "$image" | awk '{print $1}')
Candidate kernel Image SHA256: $(sha256sum "$tmp/kernel" | awk '{print $1}')
Preserved G965F DTB SHA256: $(sha256sum "$tmp/original-G965F-dtb" | awk '{print $1}')
Kernel build run ID: ${BUILD_RUN_ID:-unknown}
EOF
mkdir -p "$(dirname "$output")"
(cd "$tmp/repack" && zip -q -r -X "$output" .)
unzip -t "$output" >/dev/null
echo "Experimental G965F-only installer built: $output"
