import sys
import pathlib
import re

p4a = sys.argv[1]

# Cython recipe -> 3.0.11
c = pathlib.Path(f"{p4a}/pythonforandroid/recipes/cython/__init__.py")
if c.exists():
    t = c.read_text()
    t = re.sub(r"(?<=version = ')[^']*","3.0.11", t, count=1)
    c.write_text(t)
    print("cython -> 3.0.11")

# libx264 recipe -> os.chdir + chmod +x all .sh scripts
p = pathlib.Path(f"{p4a}/pythonforandroid/recipes/libx264/__init__.py")
if not p.exists():
    print("libx264 recipe not found, skipping")
else:
    t = p.read_text()
    m = re.search(
        r"\n    def build_arch\(self, arch\):\n        with "
        r"current_directory\(self\.get_build_dir\(arch\.arch\)\):",
        t,
    )
    if not m:
        print("libx264 build_arch pattern not matched, skipping")
    else:
        repl = (
            "\n    def build_arch(self, arch):\n"
            "        import os, stat\n"
            "        build_dir = self.get_build_dir(arch.arch)\n"
            "        os.chdir(build_dir)\n"
            '        for root, dirs, files in os.walk(build_dir):\n'
            "            for fn in files:\n"
            '                if fn.endswith(".sh") or fn in '
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
        print("libx264 recipe: os.chdir + chmod +x .sh")
