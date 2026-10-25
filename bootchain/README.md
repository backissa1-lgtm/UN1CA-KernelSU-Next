# G965F all-in-one KernelSU Next + NeoZygisk + Vector

Target: Samsung Galaxy S9+ **SM-G965F**, UN1CA Android 16 / One UI 8,
KernelSU Next, SUSFS 1.5.5, SELinux Enforcing.

The **kernel itself** was boot-tested. The user confirmed the following
software stack worked on their phone after the repairs below. This new
**combined recovery + first-boot automatic installer is NOT yet flash-tested**.

## Exact official package versions (pinned SHA256)

The GitHub workflow downloads and verifies all four official release files
by SHA-256 and the upstream KernelSU ARM64 BusyBox by its pinned Git blob ID
([asset manifest](assets.manifest)); it bundles them into the kernel ZIP. No network access on the phone is needed during installation.

- KernelSU Next **v3.4.2** standard manager
  (`KernelSU_Next_v3.4.2-50-gb427a3f9_33405-release.apk`, not spoofed)
- KernelSU Next **v3.4.2** ARM64 `ksud-aarch64-linux-android`
  (compatible UAPI 6 required by this kernel)
- Pinned upstream KernelSU Next **v3.4.2 ARM64 BusyBox** for fresh installs
- NeoZygisk **v2.4 (289)** official release ZIP
- Vector **v2.2 (3080)** official release ZIP

## Requested installation order

| Phase | Action |
| --- | --- |
| Recovery | 1. Flash validated SM-G965F kernel / preserve UN1CA DTB |
| Recovery, if `/data` is decrypted | 2. Clear cache, Dalvik and ART compiled-code caches only |
| Recovery, if `/data` is decrypted | 3. Stage official manager APK, compatible daemon, and both module ZIPs |
| Recovery, if `/data` is decrypted | 4. Protect UAPI 6 `/data/adb/ksud` against UN1CA's UAPI 4 copy; install one-shot bootstrap module |
| First Android boot | 5. Wait for Android PackageManager and install KernelSU Next 3.4.2 manager with `pm install -r` |
| First Android boot | 6. Install NeoZygisk v2.4 and Vector v2.2 through `ksud module install` |
| First Android boot | 7. Apply NeoZygisk and Vector startup fixes to both active and pending modules |
| Automatic reboot | 8. Reboot once to activate Zygisk and Vector |

**The APK cannot be installed in recovery.** Android PackageManager is not
running there. The KernelSU boot service performs this step later.

**This is not a no-data-required installer.** Recovery must have decrypted
and writable `/data/adb`. The ZIP provisions its pinned ARM64 BusyBox if
the device does not have one already; this is used to protect the compatible
daemon on F2FS. If `/data` is inaccessible, the kernel can still flash but
automatic userspace setup will be skipped. The hook prints a message and
recovery keeps `/tmp/g965f-bootchain-install.log` when staging is attempted.
Do **not** assume modules installed from a successful kernel flash alone.
A clean/new phone without those prerequisites needs additional provisioning.

## Confirmed working on-device repairs

1. **UAPI 4 vs UAPI 6:** UN1CA
   `/system/etc/init/unica_ksunext_installer.rc` executes
   `copy /system/bin/ksud /data/adb/ksud` during post-fs-data.
   UN1CA's UAPI 4 daemon prevents KernelSU services from running against
   the UAPI 6 kernel. The user preserved a working UAPI 6 daemon and used
   F2FS `busybox chattr +i` to prevent overwrite. The original successful
   on-device daemon was `ksud 3.4.2-50-gb427a3f9 (uapi: 6)`. The
   official v3.4.2 release is bundled as a fallback on newly provisioned
   devices, and the running version must be verified after boot.
2. **NeoZygisk double initialization:** repeated calls to
   `post-fs-data.sh` deleted `/data/adb/neozygisk/cp64.sock` while
   `zygiskd64` remained running. Three monitors accumulated.
   The guard in `bootchain/apply.sh` skips duplicate calls if the
   `zygisk-ptrace64` or 32-bit monitor already exists. One monitor
   remained after reboot, the socket existed and the errors disappeared.
3. **Vector launch:** Android `unshare` does not support
   `--propagation slave`. The repaired `service.sh` uses KernelSU
   BusyBox `unshare`, avoids starting a second `vectord`, and uses
   `--system-server-max-retry=0` (the configuration the user tested).
   Vector's working daemon reported v2.2 (3080) and API 102.

If the ZIP is flashed from **running Android** rather than recovery, it
stages files but defers destructive cache clearing; do not delete active
ART caches while applications are running.

## Rollback, updates, diagnostics

`bootchain/recovery-stage.sh`: only for post-flash recovery with decrypted
`/data`. `bootchain/first-boot.sh`: run by the one-shot
`g965f_bootchain_setup` KernelSU module when Android finishes booting.
`bootchain/apply.sh`: repeatable startup patches for NeoZygisk and Vector,
including `/data/adb/modules_update` before the second reboot.

Check staged progress in
`/data/adb/g965f-bootchain/setup.log`. The marker
`/data/adb/g965f-bootchain/setup.done` is written only once the manager,
modules, and patches have succeeded. If setup fails, the module tries again
at the next normal boot; it does not erase app data.

Check the results:

```sh
su
cat /data/adb/g965f-bootchain/setup.log
/data/adb/ksud --version
/data/adb/ksu/bin/busybox lsattr /data/adb/ksud
cat /data/adb/neozygisk/module.prop
ls -l /data/adb/neozygisk/cp64.sock
ps -A | grep -E 'zygisk-ptrace64|zygiskd64|vectord'
sh /data/adb/modules/zygisk_vector/cli status
```

**Before any future KernelSU daemon update, remove immutable protection:**

```sh
su
/data/adb/ksu/bin/busybox chattr -i /data/adb/ksud
```

Then update the UAPI 6-compatible manager/daemon, re-run
`bootchain/apply.sh` and reboot. Updates of NeoZygisk or Vector may
overwrite their startup fixes; re-run the helper after any module update.

Backups of patched module files are named
`post-fs-data.sh.before-bootchain-auto` and
`service.sh.before-bootchain-auto` inside the affected module directory.
`bootchain/apply.sh` does not disable SELinux, change SUSFS, wipe
applications, or modify the ROM's read-only system partition.

## Corrected manager/daemon UAPI (October 25, 2026)

The initial all-in-one ZIP contained stable KernelSU Next v3.4.2 build
33355, compiled with **manager UAPI 5**, and its standalone daemon, also
**UAPI 5**. Our custom kernel is **UAPI 6**. The first phone flash
booted, but the manager warned it needs UAPI 6.

The corrected all-in-one package pins the **official upstream development
CI build 33405, v3.4.2-50-gb427a3f9 (UAPI 6)**, and extracts the exact
compatible ARM64 daemon from that APK. The build verifies the manager SHA256,
APK v2 certificate against the KernelSU trusted signer, and embedded daemon
SHA256 against the one that already ran successfully on-device. If upstream
CI artifact access fails, the build fails rather than substituting UAPI 5.

The old all-in-one ZIP should not be reused for new installs. Existing
phones can update just the manager APK to build 33405: no reflash needed.

## Permanent Termux and app root-permission persistence fix

The user confirmed that `/data/adb/ksu/.allowlist` contained the permitted
Termux profile (`com.termux`, UID 10320), and Linux logged a successful
`save allow list`. On every reboot, at post-fs-data, the kernel instead
logged `allowlist file invalid: 0!` and `ksud profile get com.termux`
returned `stored: false`, `allow_su: false`. The file and termux record
were still present; permission pruning was not responsible.

**Cause:** SM-G965F uses Linux **4.9.337**, where `kernel_read()` takes the
old argument signature. KernelSU legacy commit `0b17f242` mistakenly
called the 4.14+ `kernel_read(file, buffer, count, &offset)` signature three
times within `ksu_load_allow_list()`. It already supplies a helper
`ksu_kernel_read_compat()` that selects the correct argument order on 4.9.
The save routine already uses `ksu_kernel_write_compat()`.

At compile time, `scripts/fix_ksu_allowlist_persistence.py` converts
the three allowlist reads (magic, format version, and profile) to
`ksu_kernel_read_compat()`. Verification requires all three conversions,
and the CI regression test exercises this patch. It does **not** write
the saved allowlist, grant root to any app, suppress profile validation, or
change SELinux. Existing app permissions should be restored automatically.

**Validation still needed on-device:** On the patched ZIP, grant Termux
root once, verify `/data/adb/ksud profile get com.termux` shows
`stored: true` and `allow_su: true`, reboot, and verify the same values
without opening the manager. The boot log should show `allowlist version: 4`
and `load_allow_uid, name: com.termux` instead of `allowlist file invalid`.
