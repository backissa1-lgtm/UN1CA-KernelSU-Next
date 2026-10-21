#!/usr/bin/env bash
# Package an experimental G965F Image using the UN1CA maintainer's proven installer.
# The tested DTB and the current device's ramdisk are preserved.
set -euo pipefail
if [ "$#" -ne 3 ]; then
  echo "usage: $0 ROM-maintainer-erofs.zip candidate-G965F-boot.img output.zip" >&2
  exit 2
fi
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
source_zip="$(realpath "$1")"
candidate_img="$(realpath "$2")"
out="$(realpath -m "$3")"
expected_sha="3e405a08fd5e0b4f8492096be9003349bb8372e4f16ec43f0308095d6615203f"
echo "$expected_sha  $source_zip" | sha256sum --check
for cmd in unzip zip bsdiff bspatch python3; do command -v "$cmd" >/dev/null; done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
unzip -q "$source_zip" -d "$tmp/repack"
python3 "$repo_root/scripts/extract_android_boot_v0.py" \
  "$candidate_img" "$tmp/new-kernel" "$tmp/new-dtb" > "$tmp/image-metadata.json"

base="$tmp/repack/floyd/G960F-kernel"
patch="$tmp/repack/floyd/G965F-kernel"
test -s "$base" && test -s "$patch" && test -s "$tmp/repack/floyd/G965F-dtb"
# Rewrite ONLY the G965F kernel delta. Preserve proven G965F-dtb unchanged.
bsdiff "$base" "$tmp/new-kernel" "$patch"
bspatch "$base" "$tmp/reconstructed-kernel" "$patch"
cmp "$tmp/new-kernel" "$tmp/reconstructed-kernel"
# Verify maintainer's original DTB delta still reconstructs successfully.
bspatch "$tmp/repack/floyd/G960F-dtb" "$tmp/maintainer-G965F-dtb" \
  "$tmp/repack/floyd/G965F-dtb"
test -s "$tmp/maintainer-G965F-dtb"
python3 - "$tmp/repack/META-INF/com/google/android/update-binary" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
old="if echo $device | grep '[GN]96[05][FN]'; then"
new="if echo $device | grep 'G965F'; then"
assert s.count(old)==1, "Unexpected installer; refusing broad flashing support"
s=s.replace(old,new)
s=s.replace('DS-ACK-V1.12-01.10.2026-KernelSU Installer',
            'EXPERIMENTAL UN1CA G965F KernelSU Next Installer')
s=s.replace('DS-ACK-V1.12-01.10.2026-KernelSU Installed',
            'EXPERIMENTAL G965F kernel installed')
p.write_text(s)
PY
cat > "$tmp/repack/BUILD-NOTES.txt" <<EOF
EXPERIMENTAL TEST PACKAGE; not boot-tested on actual device.
Device: Samsung SM-G965F / star2lte only.
Original maintainer package sha256: $expected_sha
Original installer and G965F DTB retained; only G965F kernel patch changed.
Original device ramdisk will be preserved by the inherited update-binary.
Candidate Android boot image sha256: $(sha256sum "$candidate_img" | awk '{print $1}')
Candidate kernel Image sha256: $(sha256sum "$tmp/new-kernel" | awk '{print $1}')
Candidate DTB sha256 (NOT FLASHED): $(sha256sum "$tmp/new-dtb" | awk '{print $1}')
Original G965F DTB sha256 (FLASHED): $(sha256sum "$tmp/maintainer-G965F-dtb" | awk '{print $1}')
EOF
mkdir -p "$(dirname "$out")"
(cd "$tmp/repack" && zip -q -r -X "$out" .)
unzip -t "$out" >/dev/null
echo "Experimental package created at: $out"
du -h "$out"
