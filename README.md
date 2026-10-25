# UN1CA S9+ KernelSU Next + SUSFS

Target: Samsung S9+ SM-G965F (star2lte, Exynos 9810), UN1CA Android 16 / One UI 8, Linux 4.9.337, EROFS, SELinux Enforcing.

**Status: the base kernel booted on the target phone with KernelSU Next UAPI 6, NeoZygisk and Vector. The new all-in-one recovery + first-boot installer on this side branch has NOT yet been flash-tested.**

Pinned source:
- Eend15/exynos9810-kernel @ 8f29b4e0e977d521bb5866ad167b391bea2988c9 (October 1, 2026)
- KernelSU-Next/KernelSU-Next legacy @ 0b17f24246db5c80c056b92c15bcad2b77f1276e (October 17, 2026)

The UN1CA ROM [maintainer documentation](https://github.com/Eend15/Unofficial-Un1ca-9810/blob/Android-16/platform/exynos9810/prebuilt/README.md) reports a boot-tested October 14 G965F kernel with KernelSU Next v3.4.0 and SUSFS. The published October 1 source is not necessarily the source of that exact binary.

The active legacy KernelSU Next **driver integration** is the appropriate starting point for Linux 4.9. The modern v3.4.2 GKI driver is NOT a drop-in replacement. "Legacy" describes integration, not necessarily an old manager version.

The [build workflow](../../actions/workflows/kernel.yml) fetches the pinned sources, generates a comparison, then attempts baseline and updated-driver G965F builds while checking that SUSFS remains enabled. Both produce ONLY UNVERIFIED build artifacts. No image will be treated as safe to flash until compatibility and boot testing are complete.

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
