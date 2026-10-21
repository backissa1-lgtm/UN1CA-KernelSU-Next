#!/usr/bin/env python3
"""Bring upstream KernelSU Next feature init/exit into Eend15's retained init.c.

Do not replace Eend15's init.c: it preserves UN1CA boot/manager fixes.
No claims of enabled preinit if KSU_NO_PREINIT is set by the Kbuild.
"""
from pathlib import Path
import sys

p = Path(sys.argv[1])
src = p.read_text()
def once(before: str, after: str):
    global src
    if src.count(before) != 1:
        raise SystemExit(f"Expected exactly one occurrence of {before!r}, got {src.count(before)}")
    src = src.replace(before, after, 1)

once('#include "feature/adb_root.h"',
     '#include "feature/shell_su_adb_only.h"\n#include "preinit/preinit.h"\n#include "feature/adb_root.h"')
once('\tksu_adb_root_init();\n',
     '\tksu_adb_root_init();\n\n\tksu_shell_su_adb_only_init();\n\n\tksu_feature_apply_forced();\n')
once('\t\tksu_ksud_init();\n',
     '\t\tksu_ksud_init();\n\n\t\tksu_preinit_init();\n')
once('\tif (!ksu_late_loaded)\n\t\tksu_ksud_exit();',
     '\tif (!ksu_late_loaded) {\n\t\tksu_ksud_exit();\n\t\tksu_preinit_exit();\n\t}')
once('\tksu_adb_root_exit();\n',
     '\tksu_adb_root_exit();\n\n\tksu_shell_su_adb_only_exit();\n')
p.write_text(src)
print("Ported upstream shell-su restriction, forced feature handling and preinit hooks")
