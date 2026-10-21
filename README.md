# UN1CA S9+ KernelSU Next + SUSFS

Target: Samsung S9+ SM-G965F (star2lte, Exynos 9810), UN1CA Android 16 / One UI 8, Linux 4.9.337, EROFS, SELinux Enforcing.

**Status: experimental source-build project. No boot-validated ZIP yet.**

Pinned source:
- Eend15/exynos9810-kernel @ 8f29b4e0e977d521bb5866ad167b391bea2988c9 (October 1, 2026)
- KernelSU-Next/KernelSU-Next legacy @ 0b17f24246db5c80c056b92c15bcad2b77f1276e (October 17, 2026)

The UN1CA ROM [maintainer documentation](https://github.com/Eend15/Unofficial-Un1ca-9810/blob/Android-16/platform/exynos9810/prebuilt/README.md) reports a boot-tested October 14 G965F kernel with KernelSU Next v3.4.0 and SUSFS. The published October 1 source is not necessarily the source of that exact binary.

The active legacy KernelSU Next **driver integration** is the appropriate starting point for Linux 4.9. The modern v3.4.2 GKI driver is NOT a drop-in replacement. "Legacy" describes integration, not necessarily an old manager version.

The [build workflow](../../actions/workflows/kernel.yml) fetches the pinned sources, generates a comparison, then attempts baseline and updated-driver G965F builds while checking that SUSFS remains enabled. Both produce ONLY UNVERIFIED build artifacts. No image will be treated as safe to flash until compatibility and boot testing are complete.

Both Enforcing and Permissive DS-ACK V3.2.1-susfs2 builds were already tested by the user and bootlooped at the first logo, so those binaries are excluded.
