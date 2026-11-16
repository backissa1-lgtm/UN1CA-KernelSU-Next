# UN1CA S9+ KernelSU Next + SUSFS

Target: Samsung S9+ SM-G965F (star2lte, Exynos 9810), UN1CA Android 16 / One UI 8, Linux 4.9.337, EROFS, SELinux Enforcing.

**Status: the earlier kernel booted on the target phone with KernelSU Next UAPI 6, NeoZygisk and Vector. The V1.14-based UAPI 6 candidate and its all-in-one recovery + first-boot installer have NOT yet been built or flash-tested.**

Pinned source:
- Unofficial-Un1ca-9810 Android-16 @ 4036caf75a66ee3ec2b0882ae1a192344977c931 (November 15, 2026)
- Eend15/exynos9810-kernel @ 5981121c45168ea74b12e36675d0f4532cb5aa6c (DS-ACK V1.14, November 14, 2026)
- KernelSU-Next/KernelSU-Next legacy @ 0b17f24246db5c80c056b92c15bcad2b77f1276e (October 17, 2026)

The ROM's current default EROFS kernel archive is DS-ACK V1.14, with KernelSU Next v3.4.0-legacy/UAPI 4. Its published SHA-256 is `768981b1bc670bf22f8fa8555aad2b2a7a684a5b572099a63bbbb22ba9972acc`. The V1.14 source adds the current touch wake and panel brightness fixes. The candidate workflow uses that exact source and package, then overlays the previously working v3.4.2 legacy/UAPI 6 driver. It keeps the V1.14 G965F DTB and installer.

KernelSU Next v3.4.2 **legacy** is the compatibility target for Linux 4.9. The modern v3.4.2 GKI driver is not a drop-in replacement.

The [build workflow](../../actions/workflows/enforcing-ksud-selinux-exec.yml) fetches the pinned sources, reapplies the proven Linux 4.9 and UN1CA compatibility patches, builds only the SM-G965F kernel Image, and packages it against the verified V1.14 EROFS ZIP. It preserves the V1.14 DTB, current SELinux hooks, UAPI 6 daemon protection, NeoZygisk and Vector setup. Outputs remain unverified until the new candidate boots on the phone.

Both Enforcing and Permissive DS-ACK V3.2.1-susfs2 builds were already tested by the user and bootlooped at the first logo, so those binaries are excluded.

## Working boot chain and automated all-in-one installation

Branch: `g965f-working-bootchain-auto-fixes`.

The combined G965F ZIP bundles SHA-pinned official **KernelSU Next 3.4.2
manager and ARM64 daemon**, **NeoZygisk 2.4 (289)**, **Vector 2.2 (3080)** and
a verified upstream ARM64 BusyBox. The recovery success hook installs the
compatible UAPI 6 daemon and stages Android first-boot installation, wipes
only offline cache/Dalvik/ART compiled-code caches, and preserves SELinux
Enforcing. The first-boot service installs the APK and modules, patches the
previously observed startup bugs, and reboots once.

**Auto-setup requires writable/decrypted `/data` from recovery.** On a
recovery that cannot decrypt userdata, the kernel installer may succeed but
the APK/modules are not yet installed. This new integration is not
device-tested; do not represent the first GitHub Actions ZIP as a verified
one-click installation.

Technical details, verification and rollback:
[`bootchain/README.md`](bootchain/README.md).

**Important all-in-one correction (Oct 25):** Stable manager v3.4.2
build 33355 is UAPI 5, but this kernel requires UAPI 6. The revised
branch pins upstream signed dev CI manager build 33405 and its exactly
matching UAPI 6 daemon; old all-in-one ZIPs should not be reused.
