# G965F confirmed-working boot chain (UN1CA Android 16 / One UI 8)

This side branch starts at the G965F kernel build whose **kernel booted** and whose
KernelSU/NeoZygisk/Vector stack was subsequently repaired successfully on-device
(October 25, 2026). The integrated **recovery installer hook is new and not yet
flash-tested**, so the ZIP is not a verified one-step recovery installer until
its behavior is checked on the phone.

## What went wrong and what this branch captures

1. **KernelSU daemon UAPI mismatch.** The UN1CA read-only EROFS
   `/system/etc/init/unica_ksunext_installer.rc` performs
   `copy /system/bin/ksud /data/adb/ksud` on `post-fs-data`. Its
   `/system/bin/ksud` is v3.4.0 **UAPI 4**; the working kernel expects
   **UAPI 6**. This caused `UAPI version mismatch: kernel=6, ksud=4;
   skip on_services`. Once the UAPI 6 daemon was protected on F2FS with
   `busybox chattr +i /data/adb/ksud`, KernelSU's services ran.
   The on-device tested daemon was `ksud 3.4.2-50-gb427a3f9 (uapi: 6)`.
2. **Vector's `unshare`.** Android's bundled `unshare` did not accept
   `--propagation slave`; using `/data/adb/ksu/bin/busybox unshare`
   allowed its daemon to start. We retained the tested no-restart diagnostic
   service (`--system-server-max-retry=0`) and duplicate-daemon guard.
3. **NeoZygisk repeated post-fs-data.** KernelSU/UN1CA ran
   `post-fs-data.sh` multiple times. The upstream NeoZygisk 2.4
   `post-fs-data.sh` deletes `/data/adb/neozygisk` before recreating it.
   Three monitors remained running, but later applications reported
   `GetProcessFlags/ReadModules failed with 2` because `cp64.sock`
   had been unlinked. A `pidof zygisk-ptrace64` / `pidof zygisk-ptrace32`
   guard now skips repeat initialization. After reboot there was one monitor,
   one daemon, `cp64.sock` existed, and the errors disappeared.
4. **Vector.** Its daemon and CLI started, NeoZygisk status showed
   `zygote64: injected`, `daemon64: running`,
   `Modules (1): zygisk_vector`, and the user confirmed Vector worked.

## How it is installed

`scripts/package_new_candidate.sh` bundles `bootchain/apply.sh` into the
G965F ZIP and patches **only the G965F branch** of the existing
`META-INF/com/google/android/update-binary` with a hook that runs **after
the original installer exits successfully**. It preserves the original
installer's exit status. The packaging step refuses an unexpected installer
layout or an existing EXIT trap rather than guessing.

The hook automatically runs the helper **if `/data/adb/modules` is accessible
during the flash**. If recovery cannot decrypt `/data`, the kernel can still
flash, but the userland fixes are **not** applied. On the first rooted boot,
run the helper manually after extracting it from the flashed ZIP, for example:

```sh
su
unzip -p /sdcard/Download/G965F-kernel.zip bootchain/apply.sh > /data/local/tmp/g965f-apply.sh
sh /data/local/tmp/g965f-apply.sh
reboot
```

Replace `G965F-kernel.zip` with the actual ZIP file name. If Android's
`unzip` is unavailable, use `/data/adb/ksu/bin/busybox unzip -p`.
The helper is safe to rerun, checks for root and UAPI 6, backs up replaced
scripts, does not change SELinux mode, and **does not** bundle or download a
KernelSU binary. You must have a compatible UAPI 6 `ksud` already available
at `/data/adb/ksud` or `/data/adb/ksud.uapi6`; otherwise the helper stops
without substituting the older ROM daemon.

Existing installed module scripts receive backups:

- `/data/adb/modules/zygisk_vector/service.sh.before-bootchain-auto`
- `/data/adb/modules/zygisksu/post-fs-data.sh.before-bootchain-auto`

Updates or reinstallations of NeoZygisk or Vector can overwrite the patches:
rerun `apply.sh` afterward and reboot.

## Important KernelSU upgrade procedure

Immutable protection is deliberately strict. Before any KernelSU **userspace
daemon** update, run:

```sh
su
/data/adb/ksu/bin/busybox chattr -i /data/adb/ksud
```

Upgrade to a daemon compatible with the kernel (currently UAPI 6), rerun
`apply.sh` to back it up and restore protection, then reboot. Do not
reinstall the ROM's UAPI 4 `/system/bin/ksud`.

## Undo manually

Unlock `ksud` with `chattr -i`; copy back the backed-up Vector and
NeoZygisk scripts (using `cp -p`), and reboot. The helper does not modify
the ROM's read-only init RC file, the kernel's Enforcing configuration,
NeoZygisk binaries, or the SUSFS driver.

## Validation after boot

```sh
su
/data/adb/ksud --version
/data/adb/ksu/bin/busybox lsattr /data/adb/ksud
cat /data/adb/neozygisk/module.prop
ls -l /data/adb/neozygisk/cp64.sock
ps -A | grep -E 'zygisk-ptrace64|zygiskd64|vectord'
sh /data/adb/modules/zygisk_vector/cli status
logcat -d -b all | grep -Ei 'UAPI version mismatch|GetProcessFlags failed|ReadModules failed' | tail
```

No boot loop, SELinux mode change, kernel swap, root reinstallation, or
attempted `/metadata` remount is required for this helper.
