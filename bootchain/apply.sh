#!/system/bin/sh
# G965F UN1CA / KernelSU Next boot-chain repair, October 2026.
# Safe to run repeatedly, in a root shell after boot or during recovery when
# /data is decrypted. Does not alter SELinux enforcing or the kernel.
set -u
umask 022

TAG=G965FBootchain
KSU=/data/adb/ksud
KSU_BACKUP=/data/adb/ksud.uapi6

say() { echo "$TAG: $*"; }
fail() { say "ERROR: $*"; exit 1; }
valid_ksud() {
  [ -f "$1" ] && [ -x "$1" ] &&
    "$1" --version 2>&1 | grep -q 'uapi: 6'
}
bb() {
  if [ -x /data/adb/ksu/bin/busybox ]; then
    /data/adb/ksu/bin/busybox "$@"
  elif command -v busybox >/dev/null 2>&1; then
    busybox "$@"
  else
    "$@"
  fi
}
immutable() {
  bb lsattr "$1" 2>/dev/null | awk '{print $1}' | grep -q 'i'
}
backup_once() {
  [ -f "$1" ] || return 1
  [ -f "$2" ] || cp -p "$1" "$2"
}
replace_from_tmp() {
  target="$1"
  tmp="$2"
  chmod 0755 "$tmp" || return 1
  if cmp -s "$target" "$tmp" 2>/dev/null; then
    rm -f "$tmp"
  else
    # Write to the existing inode to preserve the module's standard path.
    cat "$tmp" > "$target" || return 1
    chmod 0755 "$target" || return 1
    rm -f "$tmp"
  fi
}
[ "$(id -u)" = 0 ] || fail "root required"
[ -d /data/adb ] || fail "/data/adb is not available; rerun after boot"
[ -d /data/adb/modules ] || fail "KernelSU modules unavailable; rerun after boot"

say "checking userspace UAPI 6"
if valid_ksud "$KSU"; then
  if ! valid_ksud "$KSU_BACKUP"; then
    cp -p "$KSU" "$KSU_BACKUP" || fail "cannot preserve UAPI 6 daemon"
    chmod 0755 "$KSU_BACKUP"
    command -v chcon >/dev/null 2>&1 &&
      chcon u:object_r:ksu_file:s0 "$KSU_BACKUP" 2>/dev/null || :
  fi
elif valid_ksud "$KSU_BACKUP"; then
  # Recover from a ROM overwrite only when a compatible saved binary exists.
  if immutable "$KSU"; then
    bb chattr -i "$KSU" || fail "cannot unlock old daemon"
  fi
  cp -p "$KSU_BACKUP" "$KSU" || fail "cannot restore daemon"
  chmod 0755 "$KSU" || fail "cannot chmod daemon"
  command -v chcon >/dev/null 2>&1 &&
    chcon u:object_r:ksu_file:s0 "$KSU" 2>/dev/null || :
else
  fail "no verified UAPI 6 daemon installed; update KernelSU Next userspace first"
fi

# UN1CA's read-only EROFS init.rc repeatedly copies UAPI 4 from /system/bin.
# Preserve the compatible daemon with the F2FS immutable attribute, validated
# on the target device. Must be unlocked before updating KernelSU Next userspace.
if ! immutable "$KSU"; then
  bb chattr +i "$KSU" || fail "cannot protect UAPI 6 daemon (F2FS chattr +i)"
fi
immutable "$KSU" || fail "daemon remains writable"
say "UAPI 6 daemon protected from UN1CA boot overwrite"

# Newly installed KernelSU modules may be pending under modules_update.
for MODULE_BASE in /data/adb/modules /data/adb/modules_update; do
[ -d "$MODULE_BASE" ] || continue
VECTOR="$MODULE_BASE/zygisk_vector"
NEO="$MODULE_BASE/zygisksu"
if [ -f "$VECTOR/service.sh" ]; then
  backup_once "$VECTOR/service.sh" "$VECTOR/service.sh.before-bootchain-auto" ||
    fail "cannot back up Vector service"
  tmp="$VECTOR/service.sh.g965f-tmp"
  cat > "$tmp" <<'EOS'
#!/system/bin/sh
MODDIR="${0%/*}"
BB=/data/adb/ksu/bin/busybox
LOG=/data/local/tmp/vector-boot-trace.log
echo "$(date) SERVICE ENTERED uid=$(id -u) context=$(id -Z)" >> "$LOG"
cd "$MODDIR" || exit 1
if pidof vectord >/dev/null 2>&1; then
  echo "$(date) DAEMON ALREADY RUNNING" >> "$LOG"
  exit 0
fi
if [ ! -x "$BB" ]; then
  echo "$(date) BUSYBOX MISSING" >> "$LOG"
  exit 1
fi
(
  "$BB" unshare --propagation slave -m "$MODDIR/daemon" --system-server-max-retry=0 >> "$LOG" 2>&1
  echo "$(date) DAEMON EXIT CODE=$?" >> "$LOG"
) &
echo "$(date) DAEMON SPAWNED PID=$!" >> "$LOG"
EOS
  /system/bin/sh -n "$tmp" || fail "Vector script syntax validation failed"
  replace_from_tmp "$VECTOR/service.sh" "$tmp" ||
    fail "cannot install Vector startup fix"
  say "Vector startup fixed (BusyBox unshare; no forced system_server restart)"
else
  say "Vector not installed; skipped Vector patch"
fi

if [ -f "$NEO/post-fs-data.sh" ]; then
  neo_script="$NEO/post-fs-data.sh"
  if grep -q 'Duplicate post-fs-data skipped' "$neo_script"; then
    say "NeoZygisk duplicate-start guard already installed"
  else
    backup_once "$neo_script" "$neo_script.before-bootchain-auto" ||
      fail "cannot back up NeoZygisk startup script"
    first_line="$(head -n 1 "$neo_script")"
    [ "$first_line" = '#!/system/bin/sh' ] ||
      fail "unexpected NeoZygisk startup script header"
    tmp="$neo_script.g965f-tmp"
    {
      printf '#!/system/bin/sh\n\n'
      cat <<'EOS'
# KernelSU on UN1CA invokes post-fs-data multiple times.
# NeoZygisk's upstream script deletes its workdir and IPC socket each time.
if pidof zygisk-ptrace64 >/dev/null 2>&1 ||
   pidof zygisk-ptrace32 >/dev/null 2>&1; then
  log -p i -t NeoZygisk "Duplicate post-fs-data skipped"
  exit 0
fi

EOS
      tail -n +2 "$neo_script"
    } > "$tmp"
    /system/bin/sh -n "$tmp" || fail "NeoZygisk script syntax validation failed"
    replace_from_tmp "$neo_script" "$tmp" ||
      fail "cannot install NeoZygisk duplicate-start guard"
    say "NeoZygisk duplicate-start guard installed"
  fi
else
  say "NeoZygisk not installed; skipped NeoZygisk patch"
fi
done
say "boot-chain setup complete; reboot to activate module scripts"
exit 0
