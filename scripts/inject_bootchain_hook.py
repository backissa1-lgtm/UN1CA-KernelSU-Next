#!/usr/bin/env python3
"""Add a G965F-only successful-flash EXIT hook to UN1CA's update-binary.

The original installer is preserved, including its exit status. Applying
userland fixes is best-effort because custom recoveries may not decrypt /data.
This build step aborts if the original selector/layout no longer matches.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: inject_bootchain_hook.py path/to/update-binary")
p = Path(sys.argv[1])
src = p.read_text(errors="replace")
marker = "if echo $device | grep 'G965F'; then"
sentinel = "G965F_BOOTCHAIN_INTEGRATION_V1"
if src.count(marker) != 1:
    raise SystemExit("Unknown installer device-selection layout")
if sentinel in src:
    raise SystemExit("Installer hook already present")
if not src.startswith("#!"):
    raise SystemExit("Expected POSIX shell installer; refusing binary installer")
if any(("trap " in line and ("EXIT" in line or " 0" in line))
       for line in src.splitlines() if not line.lstrip().startswith("#")):
    raise SystemExit("Existing EXIT trap; manual composition required")

function = '''
# G965F_BOOTCHAIN_INTEGRATION_V1
# Called only on successfully completed G965F flash. Failure to apply
# userland fixes must never change the original kernel installer result.
g965f_bootchain_on_exit() {
    g965f_installer_status="$1"
    trap - 0
    if [ "$g965f_installer_status" -eq 0 ]; then
        if [ -d /data/adb/modules ] && [ -n "$G965F_BOOTCHAIN_ZIP" ]; then
            if unzip -p "$G965F_BOOTCHAIN_ZIP" bootchain/recovery-stage.sh > /tmp/g965f-bootchain-apply.sh; then
                echo "G965F boot-chain: applying on-device fixes"
                sh /tmp/g965f-bootchain-apply.sh "$G965F_BOOTCHAIN_ZIP" \
                    > /tmp/g965f-bootchain-install.log 2>&1 ||
                    echo "G965F boot-chain: recovery staging incomplete; see /tmp/g965f-bootchain-install.log"
                cat /tmp/g965f-bootchain-install.log 2>/dev/null || :
            else
                echo "G965F boot-chain: cannot extract recovery stage"
            fi
        else
            echo "G965F boot-chain: /data/adb unavailable; first-boot auto-install is not staged"
        fi
    fi
    exit "$g965f_installer_status"
}
'''
line_end = src.find("\n")
if line_end < 0:
    raise SystemExit("Missing shebang newline")
src = src[:line_end + 1] + function + src[line_end + 1:]
src = src.replace(marker, marker +
                  '\n  G965F_BOOTCHAIN_ZIP="$3"\n' +
                  "  trap 'g965f_bootchain_on_exit $?' 0\n", 1)
p.write_text(src)
assert src.count(sentinel) == 1
assert src.count("g965f_bootchain_on_exit $?") == 1
print("Installed G965F-only post-success boot-chain helper hook")
