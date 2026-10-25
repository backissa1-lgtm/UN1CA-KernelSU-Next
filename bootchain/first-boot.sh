#!/system/bin/sh
# KernelSU 'service' stage, after the new G965F kernel boots.
# Installs manager via Android PM, then official NeoZygisk/Vector module ZIPs.
# A single automatic reboot activates the modules after their scripts are fixed.
set -u
STAGE=/data/adb/g965f-bootchain
ASSETS="$STAGE/assets"
KSU=/data/adb/ksud
DONE="$STAGE/setup.done"
LOCK="$STAGE/setup.lock"
say() { echo "$(date) FIRST-BOOT: $*"; }
fail() { say "ERROR: $*"; exit 1; }

[ "$(id -u)" = 0 ] || fail "root required"
[ -d "$ASSETS" ] || fail "recovery did not stage official assets"
[ -f "$DONE" ] && exit 0

# Avoid racing KernelSU's repeated 'services' events.
if ! mkdir "$LOCK" 2>/dev/null; then
  oldpid="$(cat "$LOCK/pid" 2>/dev/null || :)"
  if [ -n "$oldpid" ] && kill -0 "$oldpid" 2>/dev/null; then
    say "another first-boot installer is running"
    exit 0
  fi
  rm -rf "$LOCK" 2>/dev/null || fail "cannot clear stale installer lock"
  mkdir "$LOCK" || fail "cannot acquire lock"
fi
echo "$$" > "$LOCK/pid"
trap 'rm -rf "$LOCK"' 0
trap 'exit 1' 1 2 3 15

say "waiting for Android PackageManager"
counter=0
until [ "$(getprop sys.boot_completed)" = 1 ] && pm path android >/dev/null 2>&1; do
  counter=$((counter + 1))
  [ "$counter" -lt 180 ] || fail "Android boot incomplete (timeout); retry next boot"
  sleep 2
done

say "checking KernelSU Next daemon version"
ver="$("$KSU" --version 2>&1)"
say "$ver"
echo "$ver" | grep -q 'uapi: 6' || fail "daemon is not UAPI 6"

say "installing official signed KernelSU Next UAPI6 dev manager 33405"
apk="$ASSETS/KernelSU_Next_v3.4.2-50-gb427a3f9_33405-release.apk"
[ -f "$apk" ] || fail "manager APK missing"
# PackageManager's shell process may not be able to traverse /data/adb.
# Copy the verified APK into /data/local/tmp with shell-readable permissions.
tmpapk=/data/local/tmp/G965F-KernelSU-Next-3.4.2.apk
cp -p "$apk" "$tmpapk" || fail "cannot stage manager for PackageManager"
chmod 0644 "$tmpapk" || fail "cannot set manager APK permissions"
chcon u:object_r:shell_data_file:s0 "$tmpapk" 2>/dev/null || :
# -r updates the existing trusted package; Android verifies the APK signature.
# Do not uninstall an existing manager or bypass signature checks.
pm install -r "$tmpapk" || fail "PackageManager rejected manager APK"
rm -f "$tmpapk" 2>/dev/null || :
pm path com.rifsxd.ksunext >/dev/null 2>&1 ||
  fail "KernelSU Next manager package was not installed"
say "manager APK verified installed"

install_mod() {
  id="$1"
  expected="$2"
  zip="$3"
  # KernelSU may already have staged a module for next boot.
  for path in "/data/adb/modules_update/$id" "/data/adb/modules/$id"; do
    if [ -f "$path/module.prop" ] &&
       grep -q "^version=$expected" "$path/module.prop"; then
      say "$id $expected already installed; retaining existing settings"
      return 0
    fi
  done
  [ -f "$ASSETS/$zip" ] || fail "$zip missing"
  say "installing $id $expected"
  "$KSU" module install "$ASSETS/$zip" ||
    fail "KernelSU module install failed: $id"
  # Fresh modules might be written into modules_update and become active on
  # the next boot. The repair helper patches BOTH directories.
  if [ ! -f "/data/adb/modules_update/$id/module.prop" ] &&
     [ ! -f "/data/adb/modules/$id/module.prop" ]; then
    fail "$id not present after KernelSU module install"
  fi
}

install_mod zygisksu 'v2.4 (289-' NeoZygisk-v2.4-289-release.zip
install_mod zygisk_vector 'v2.2 (3080-' Vector-v2.2-3080-Release.zip

say "applying working NeoZygisk and Vector startup repairs"
/system/bin/sh "$STAGE/apply.sh" || fail "startup repair failed"
for id in zygisksu zygisk_vector; do
  found=0
  for path in "/data/adb/modules_update/$id" "/data/adb/modules/$id"; do
    [ -f "$path/module.prop" ] && found=1
  done
  [ "$found" -eq 1 ] || fail "missing $id after repairs"
done
say "all components installed, patched, and staged for next boot"
touch "$DONE" || fail "cannot record setup success"
sync
say "one-time reboot to activate NeoZygisk and Vector"
sleep 3
reboot
exit 0
