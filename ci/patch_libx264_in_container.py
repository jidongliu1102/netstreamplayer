import pathlib, re
p = pathlib.Path("/app/.buildozer/android/platform/python-for-android/pythonforandroid/recipes/libx264/__init__.py")
t = p.read_text()
m = re.search(
    r"\n    def build_arch\(self, arch\):\n        with "
    r"current_directory\(self\.get_build_dir\(arch\.arch\)\):",
    t,
)
if not m:
    print("NO MATCH")
    import sys
    sys.exit(1)
repl = (
    "\n    def build_arch(self, arch):\n"
    "        import os, stat\n"
    "        build_dir = self.get_build_dir(arch.arch)\n"
    "        os.chdir(build_dir)\n"
    "        for root, dirs, files in os.walk(build_dir):\n"
    "            for fn in files:\n"
    "                if fn.endswith(\".sh\") or fn in "
    '("configure","config.sub","config.guess","version.sh"):\n'
    "                    fp = os.path.join(root, fn)\n"
    "                    try:\n"
    "                        st = os.stat(fp)\n"
    "                        os.chmod(fp, st.st_mode |\n"
    "                            stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)\n"
    "                    except Exception:\n"
    "                        pass\n"
    "        with current_directory(self.get_build_dir(arch.arch)):\n"
)
t = t[:m.start()] + repl + t[m.end():]
p.write_text(t)
print("PATCHED OK")
