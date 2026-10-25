#!/usr/bin/env bash
set -euo pipefail
bash -n bootchain/apply.sh
python3 -m py_compile scripts/inject_bootchain_hook.py

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/update-binary" <<'EOS'
#!/system/bin/sh
device=G965F
if echo $device | grep 'G965F'; then
    echo "Kernel installed"
fi
EOS
python3 scripts/inject_bootchain_hook.py "$tmp/update-binary"
bash -n "$tmp/update-binary"
grep -q G965F_BOOTCHAIN_INTEGRATION_V1 "$tmp/update-binary"

# Hook insertion is fail-closed if repeated or on an unexpected installer.
if python3 scripts/inject_bootchain_hook.py "$tmp/update-binary"; then
  echo "Duplicate hook unexpectedly accepted" >&2
  exit 1
fi
cat > "$tmp/not-our-installer" <<'EOS'
#!/system/bin/sh
echo "Unexpected installer"
EOS
if python3 scripts/inject_bootchain_hook.py "$tmp/not-our-installer"; then
  echo "Unexpected installer layout accepted" >&2
  exit 1
fi

# The original installer exit code must remain unchanged on failure.
sed -i 's/echo "Kernel installed"/exit 19/' "$tmp/update-binary"
if sh "$tmp/update-binary" unused unused /tmp/fake.zip; then
  echo "Installer failure was masked by boot-chain hook" >&2
  exit 1
else
  test "$?" -eq 19
fi
echo "Boot-chain script and installer hook validation passed"
