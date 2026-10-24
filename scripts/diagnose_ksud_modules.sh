#!/system/bin/sh
# Read-only KernelSU Next / UN1CA module-stage diagnosis for root Termux.
# Run: su -c 'sh /sdcard/Download/diagnose_ksud_modules.sh'
# Does not copy files, chmod anything, alter modules, or replay boot stages.
export PATH=/system/bin:/system/xbin:/vendor/bin:${PATH}
set +e
echo "=== Device / SELinux ==="
getprop ro.product.model
getprop ro.build.version.release
getenforce
id
echo
echo "=== ksud binaries ==="
for bin in /system/bin/ksud /data/adb/ksud; do
  if [ -e "$bin" ]; then
    ls -lZ "$bin" 2>&1
    "$bin" --version 2>&1 | head -n 2
    sha256sum "$bin" 2>&1
  else
    echo "$bin: MISSING"
  fi
done
echo
echo "=== Module directories ==="
for dir in /data/adb/modules_update /data/adb/modules /data/adb/ksu; do
  if [ -d "$dir" ]; then
    ls -ldZ "$dir" 2>&1
    if [ "$dir" != /data/adb/ksu ]; then
      ls -A "$dir" 2>&1 | head -n 60
    fi
  else
    echo "$dir: MISSING"
  fi
done
echo
echo "=== KernelSU boot-stage kernel messages ==="
dmesg 2>&1 | grep -Ei 'KernelSU:|ksud:|on_post_fs_data|on_module_mounted|on_boot_completed|read_proxy|read_iter_proxy|read init.rc|module rc:|exec zygote|second_stage' | tail -n 100
echo
echo "=== Android init / ksud launch failures ==="
logcat -d -b all -v brief 2>&1 | grep -Ei '(/data/adb/ksud|ksud post-fs-data|ksud services|KernelSU|unica_ksunext)' | grep -Ei '(failed|denied|error|exit|post.fs.data|service|missing|start|exec)' | tail -n 80
echo
echo "Read-only diagnosis complete. Avoid publishing the entire logcat output."
