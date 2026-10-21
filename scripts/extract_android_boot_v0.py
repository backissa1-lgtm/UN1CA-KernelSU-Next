#!/usr/bin/env python3
"""Extract kernel/DTB from a Samsung Android boot.img with v0-style layout.

Do NOT attempt to parse GKI boot headers or vendor_boot images with this script.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

if len(sys.argv) != 4:
    raise SystemExit("usage: extract_android_boot_v0.py boot.img kernel-out dtb-out")
image, kernelout, dtbout = map(Path, sys.argv[1:])
data = image.read_bytes()
if data[:8] != b"ANDROID!":
    raise SystemExit("Unsupported boot image: expected AOSP ANDROID! header")
kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr, tags_addr, page_size, dt_size, unused = struct.unpack_from("<10I", data, 8)
if page_size not in (2048, 4096, 8192, 16384):
    raise SystemExit(f"Unexpected page_size {page_size}")
if not (10_000_000 < kernel_size < 80_000_000 and 10_000 < dt_size < 4_000_000):
    raise SystemExit(f"Unexpected kernel/DTB length: kernel {kernel_size}, dtb {dt_size}")
align = lambda v: (v + page_size - 1) // page_size * page_size
pos = page_size
kernel = data[pos:pos + kernel_size]
pos += align(kernel_size) + align(ramdisk_size) + align(second_size)
dtb = data[pos:pos + dt_size]
if len(kernel) != kernel_size or len(dtb) != dt_size or not dtb.startswith(b"DTBH"):
    raise SystemExit("Kernel or Samsung DTBH content missing; refusing to package")
kernelout.parent.mkdir(parents=True, exist_ok=True)
dtbout.parent.mkdir(parents=True, exist_ok=True)
kernelout.write_bytes(kernel)
dtbout.write_bytes(dtb)
print(json.dumps({
    "boot_sha256": hashlib.sha256(data).hexdigest(),
    "kernel_sha256": hashlib.sha256(kernel).hexdigest(),
    "dtb_sha256": hashlib.sha256(dtb).hexdigest(),
    "kernel_size": kernel_size, "dtb_size": dt_size,
    "page_size": page_size, "ramdisk_size": ramdisk_size,
}, indent=2))
