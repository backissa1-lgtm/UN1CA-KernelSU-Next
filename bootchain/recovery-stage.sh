#!/system/bin/sh
# Recovery stage for G965F all-in-one KernelSU Next + Zygisk + Vector ZIP.
# This needs decrypted, writable /data. The original kernel installer exits
# successfully even when recovery cannot access /data (see bootchain docs).
set -u
ZIP="$1"
STAGE=/data/adb/g965f-bootchain
BIN=/data/adb/ksud
SAVED=/data/adb/ksud.uapi6
say() { echo "G965F package: $*"; }
fail() { say "ERROR: $*"; exit 1; }
[ "$(id -u)" = 0 ] || fail "root privileges unavailable in recovery"
[ -f "$ZIP" ] || fail "ZIP missing"
[ -d /data/adb ] && [ -w /data/adb ] ||
  fail "userdata unavailable: manual first-boot setup required"
mkdir -p /data/adb/modules "$STAGE/assets" || fail "cannot create staging area"
umask 022

# Check all four official release digests before any change to boot services.
unzip -p "$ZIP" bootchain/assets.manifest > "$STAGE/assets.manifest" ||
  fail "cannot read official hashes"
for name in KernelSU_Next_v3.4.2_33355-release.apk ksud-aarch64-linux-android NeoZygisk-v2.4-289-release.zip Vector-v2.2-3080-Release.zip busybox-aarch64; do
  digest="$(awk -v n="$name" '$1 == n { print $2 }' "$STAGE/assets.manifest")"
  [ -n "$digest" ] || fail "no checksum for $name"
  unzip -p "$ZIP" "bootchain/assets/$name" > "$STAGE/assets/$name.tmp" ||
    fail "cannot extract $name"
  if [ "$name" = busybox-aarch64 ]; then
    # The official Linux ARM64 BusyBox is pinned by its upstream Git blob ID.
    actual="$( { printf 'blob %s\0' "$(wc -c < "$STAGE/assets/$name.tmp")"; cat "$STAGE/assets/$name.tmp"; } | sha1sum | cut -d ' ' -f 1)"
  else
    actual="$(sha256sum "$STAGE/assets/$name.tmp" | cut -d ' ' -f 1)"
  fi
  [ "$actual" = "$digest" ] || fail "invalid digest for $name"
  mv -f "$STAGE/assets/$name.tmp" "$STAGE/assets/$name"
done
say "four SHA256 hashes and official BusyBox Git blob verified"

BB=/data/adb/ksu/bin/busybox
if [ ! -x "$BB" ]; then
  say "provisioning pinned upstream ARM64 BusyBox for first boot"
  mkdir -p /data/adb/ksu/bin || fail "cannot create KernelSU executable directory"
  cp -p "$STAGE/assets/busybox-aarch64" "$BB" || fail "cannot install BusyBox"
  chmod 0755 "$BB"
  chcon u:object_r:ksu_file:s0 "$BB" 2>/dev/null || :
fi
[ -x "$BB" ] || fail "cannot prepare BusyBox"

valid_ksud() {
  [ -x "$1" ] && "$1" --version 2>&1 | grep -q 'uapi: 6'
}
# Prefer the already working daemon when the system has one; otherwise install
# the verified v3.4.2 ARM64 binary to both the active and preserved paths.
if valid_ksud "$BIN"; then
  if ! valid_ksud "$SAVED"; then cp -p "$BIN" "$SAVED" || fail "save daemon"; fi
  say "preserved working UAPI 6 daemon"
elif valid_ksud "$SAVED"; then
  if [ -x "$BB" ]; then "$BB" chattr -i "$BIN" 2>/dev/null || :; fi
  cp -p "$SAVED" "$BIN" || fail "restore saved UAPI 6 daemon"
else
  if [ -x "$BB" ]; then "$BB" chattr -i "$BIN" 2>/dev/null || :; fi
  cp -p "$STAGE/assets/ksud-aarch64-linux-android" "$SAVED" ||
    fail "install official v3.4.2 daemon"
  cp -p "$SAVED" "$BIN" || fail "install active daemon"
fi
chmod 0755 "$SAVED" "$BIN" 2>/dev/null || :
chown 0:0 "$SAVED" "$BIN" 2>/dev/null || :
chcon u:object_r:ksu_file:s0 "$SAVED" "$BIN" 2>/dev/null || :
[ -x "$BB" ] || fail "KernelSU BusyBox missing: cannot guard daemon"
"$BB" chattr +i "$BIN" || fail "cannot prevent UN1CA UAPI4 overwrite"
say "UAPI 6 daemon protected"

# Place a minimal service module now: KernelSU will run it after Android starts.
# Only Android can run PackageManager; recovery cannot pm install the APK.
unzip -p "$ZIP" bootchain/first-boot.sh > "$STAGE/first-boot.sh" ||
  fail "extract first-boot service"
unzip -p "$ZIP" bootchain/apply.sh > "$STAGE/apply.sh" ||
  fail "extract startup fixes"
chmod 0755 "$STAGE/first-boot.sh" "$STAGE/apply.sh"
MOD=/data/adb/modules/g965f_bootchain_setup
mkdir -p "$MOD" || fail "cannot stage setup module"
cat > "$MOD/module.prop" <<'EOF'
id=g965f_bootchain_setup
name=G965F UN1CA First Boot Installer
version=1.0
versionCode=1
author=backissa1-lgtm
description=Installs KernelSU Next manager, NeoZygisk and Vector at first Android boot.
EOF
cat > "$MOD/service.sh" <<'EOF'
#!/system/bin/sh
STAGE=/data/adb/g965f-bootchain
[ -f "$STAGE/setup.done" ] && exit 0
# Do not keep the boot service's init process group: init kills it
# after ksud services exits. A new session survives until Android boot completes.
BB=/data/adb/ksu/bin/busybox
if [ -x "$BB" ]; then
  "$BB" setsid /system/bin/sh "$STAGE/first-boot.sh" >> "$STAGE/setup.log" 2>&1 </dev/null &
else
  /system/bin/sh "$STAGE/first-boot.sh" >> "$STAGE/setup.log" 2>&1 </dev/null &
fi
EOF
chmod 0755 "$MOD/service.sh"
touch "$MOD/skip_mount"

# Rebuildable cache only: do not erase app data or entire ART data directory.
if [ "$(getprop sys.boot_completed 2>/dev/null)" = 1 ]; then
  say "Android is running: deferring cache wipe to offline recovery"
else
  say "wiping cache, Dalvik and ART compiled-code caches"
  if [ -d /cache ] && [ ! -L /cache ]; then
    find /cache -mindepth 1 -maxdepth 1 -exec rm -rf '{}' \; 2>/dev/null || :
  fi
  for dir in /data/dalvik-cache /data/resource-cache /data/misc/apexdata/com.android.art/dalvik-cache; do
    [ -d "$dir" ] && [ ! -L "$dir" ] && rm -rf "$dir" 2>/dev/null || :
  done
fi
sync
say "Recovery preparation complete; Android first-boot setup pending"
exit 0
