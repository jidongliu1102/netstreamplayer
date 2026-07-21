#!/usr/bin/env python3
"""Fix libx264 source zip: add top-level libx264/ folder + fseeko64 (NDK r28c)."""
import zipfile, tempfile, os, shutil, sys

pkg = os.path.expanduser("~/.buildozer/android/packages")
if not os.path.isdir(pkg):
    print("packages dir not found, skipping zip fix")
    sys.exit(0)

fixed = 0
for dirpath, dirs, files in os.walk(pkg):
    for f in files:
        if "x264" not in f or not f.endswith(".zip"):
            continue
        zp = os.path.join(dirpath, f)
        print("patching", zp)
        tmp = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(zp) as z:
                z.extractall(tmp)
            extracted = os.listdir(tmp)
            if len(extracted) == 1 and os.path.isdir(os.path.join(tmp, extracted[0])):
                src = os.path.join(tmp, extracted[0])
            else:
                src = tmp
            cfg = os.path.join(src, "configure")
            if os.path.isfile(cfg):
                c = open(cfg, encoding="utf-8", errors="ignore").read()
                c = c.replace(
                    "    define fseek fseeko\n    define ftell ftello\n",
                    "    define fseek fseeko64\n    define ftell ftello64\n",
                )
                open(cfg, "w", encoding="utf-8").write(c)
                print("  fseeko64 applied")
            # Re-zip with top-level "libx264/" folder
            out = zp + ".tmp"
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as w:
                for dp, _, fs in os.walk(src):
                    for fn in fs:
                        full = os.path.join(dp, fn)
                        rel = os.path.relpath(full, src)
                        w.write(full, "libx264/" + rel)
            shutil.move(out, zp)
            print("  zip restructured as libx264/")
            fixed += 1
        finally:
            shutil.rmtree(tmp)

print("done, fixed", fixed, "zip(s)")
