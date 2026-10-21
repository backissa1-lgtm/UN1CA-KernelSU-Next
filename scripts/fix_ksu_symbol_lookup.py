#!/usr/bin/env python3
"""Backport upstream KernelSU Next symbol lookup allocations to Linux 4.9.

UN1CA's Linux 4.9.337 kernel has kvmalloc_array but not kvcalloc, and
defines KSYM_NAME_LEN in linux/kallsyms.h. Preserve zero-initialization and
overflow checks. This patch is intentionally limited to two allocations.
"""
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()
old_include = "#include <linux/slab.h>"
if s.count(old_include) != 1:
    raise SystemExit("Unexpected dispatch.c includes")
s = s.replace(old_include, old_include + "\n#include <linux/kallsyms.h>", 1)
for variable in ("names", "addrs"):
    old = f"kvcalloc(cmd.count, sizeof(*{variable}), GFP_KERNEL)"
    new = f"kvmalloc_array(cmd.count, sizeof(*{variable}), GFP_KERNEL | __GFP_ZERO)"
    if s.count(old) != 1:
        raise SystemExit(f"Expected one {variable} allocation, got {s.count(old)}")
    s = s.replace(old, new, 1)
p.write_text(s)
print("Backported KernelSU symbol lookup allocations and kallsyms header to Linux 4.9")
