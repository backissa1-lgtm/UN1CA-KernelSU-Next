#!/usr/bin/env bash
# Rebase ONLY the G965F kernel delta in an audited UN1CA installer archive.
# This preserves the tested ROM-specific G965F DTB and in-device ramdisk.
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 audited-template.zip candidate-boot.img output.zip" >&2
  exit 2
fi

source_zip="$(realpath "$1")"
candidate_img="$(realpath "$2")"
output="$(realpath -m "$3")"
root="$(cd "$(dirname "$0")/.." && pwd)"

for cmd in unzip zip bsdiff bspatch sha256sum cmp python3; do
  command -v "$cmd" >/dev/null
done

# The input is an archive produced by the successful audited template workflow.
test -s "$source_zip"
provenance="$(unzip -p "$source_zip" BUILD-NOTES.txt)"
grep -Fq 'Original maintainer package sha256: 3e405a08fd5e0b4f8492096be9003349bb8372e4f16ec43f0308095d6615203f' <<<"$provenance"
grep -Fq 'Device: Samsung SM-G965F / star2lte only.' <<<"$provenance"
grep -Fq 'Original installer and G965F DTB retained' <<<"$provenance"
unzip -t "$source_zip" > /dev/null

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/package"
unzip -q "$source_zip" -d "$tmp/package"

base="$tmp/package/floyd/G960F-kernel"
delta="$tmp/package/floyd/G965F-kernel"
dtbpatch="$tmp/package/floyd/G965F-dtb"
test -s "$base" && test -s "$delta" && test -s "$dtbpatch"

original_dtbpatch_sha="$(sha256sum "$dtbpatch" | awk '{print $1}')"
original_installer_sha="$(sha256sum "$tmp/package/META-INF/com/google/android/update-binary" | awk '{print $1}')"

python3 "$root/scripts/extract_android_boot_v0.py" \
  "$candidate_img" "$tmp/new-kernel" "$tmp/not-installed-dtb" \
  > "$tmp/extracted-image.json"

# Construct a BSDIFF40 patch from the G960F base to the NEW G965F kernel.
bsdiff "$base" "$tmp/new-kernel" "$delta"
bspatch "$base" "$tmp/reconstructed-kernel" "$delta"
cmp "$tmp/new-kernel" "$tmp/reconstructed-kernel"

test "$(sha256sum "$dtbpatch" | awk '{print $1}')" = "$original_dtbpatch_sha"
test "$(sha256sum "$tmp/package/META-INF/com/google/android/update-binary" | awk '{print $1}')" = "$original_installer_sha"

cp "$tmp/package/BUILD-NOTES.txt" "$tmp/package/TEMPLATE-LINEAGE.txt"
cat > "$tmp/package/BUILD-NOTES.txt" <<EOF
EXPERIMENTAL G965F KERNELSU NEXT DRIVER TEST -- NOT BOOT-TESTED.
Device: Samsung SM-G965F / star2lte only.
Based on maintainer package sha256: 3e405a08fd5e0b4f8492096be9003349bb8372e4f16ec43f0308095d6615203f
G965F kernel payload sha256: $(sha256sum "$tmp/new-kernel" | awk '{print $1}')
G965F original DTB patch sha256: $original_dtbpatch_sha (UNCHANGED)
UN1CA installer sha256: $original_installer_sha (UNCHANGED)
The installed phone's current ramdisk is preserved by this installer.
The provided candidate DTB was NOT installed.
Source is KernelSU Next upstream legacy-compatible integration; NOT generic GKI.
This ZIP is a boot-test candidate ONLY after compiler and source audit approval.
EOF
mkdir -p "$(dirname "$output")"
(cd "$tmp/package" && zip -q -r -X "$output" .)
unzip -t "$output" > /dev/null
echo "Rebased G965F candidate kernel onto audited working-style installer:"
sha256sum "$output"
cat "$tmp/package/BUILD-NOTES.txt"
