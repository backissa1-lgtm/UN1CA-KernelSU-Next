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
template_sha="d2ac43cad7f331aed9eebf7627f502e273ebe068e7675bf7ecc75c031fff95ca"
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
SM-G965F/star2lte, UN1CA Android 16, EROFS, Enforcing.
UN1CA source installer SHA256: $original_sha
Verified derivative ZIP SHA256: $template_sha
Only G965F-kernel patch changed; original G965F DTB retained.
Installer preserves current phone ramdisk.
Candidate boot image SHA256: $(sha256sum "$image" | awk '{print $1}')
Candidate kernel Image SHA256: $(sha256sum "$tmp/kernel" | awk '{print $1}')
Preserved G965F DTB SHA256: $(sha256sum "$tmp/original-G965F-dtb" | awk '{print $1}')
Kernel build run ID: ${BUILD_RUN_ID:-unknown}
EOF
mkdir -p "$(dirname "$output")"
(cd "$tmp/repack" && zip -q -r -X "$output" .)
unzip -t "$output" >/dev/null
echo "Experimental G965F-only installer built: $output"
