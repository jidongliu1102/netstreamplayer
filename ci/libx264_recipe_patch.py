from pythonforandroid.recipe import Recipe
from pythonforandroid.util import current_directory
from pythonforandroid.logger import shprint, info
from multiprocessing import cpu_count
from os.path import realpath
import sh

class LibX264Recipe(Recipe):
    version = '5db6aa6cab1b146e07b60cc1736a01f21da01154'
    url = 'https://code.videolan.org/videolan/x264/-/archive/{version}/x264-{version}.zip'
    built_libraries = {'libx264.a': 'lib'}

    @staticmethod
    def _strip_lfs_macros(build_dir):
        import pathlib, os
        info(f"[LFS-STRIP] entering, build_dir={build_dir}")
        ch = pathlib.Path(build_dir) / 'config.h'
        info(f"[LFS-STRIP] config.h path={ch}, exists={ch.exists()}")
        if ch.exists():
            t = ch.read_text()
            has_fs = '#define fseek fseeko' in t
            has_ft = '#define ftell ftello' in t
            info(f"[LFS-STRIP] found fseek={has_fs} ftell={has_ft}")
            t = t.replace('#define fseek fseeko', '')
            t = t.replace('#define ftell ftello', '')
            ch.write_text(t)
            info(f"[LFS-STRIP] wrote. residual fseek={('fseek' in t)} ftell={('ftell' in t)}")
        else:
            info(f"[LFS-STRIP] config.h NOT FOUND in {build_dir}")
            try:
                info(f"[LFS-STRIP] contents: {os.listdir(build_dir)[:10]}")
            except Exception as e:
                info(f"[LFS-STRIP] ls err={e}")

    def prebuild_arch(self, arch):
        info(f"[LFS-STRIP prebuild_arch] arch={arch.arch}")
        bd = self.get_build_dir(arch.arch)
        info(f"[LFS-STRIP prebuild_arch] get_build_dir returned={bd}")
        self._strip_lfs_macros(bd)

    def build_arch(self, arch):
        import os, stat
        build_dir = self.get_build_dir(arch.arch)
        os.chdir(build_dir)
        for root, dirs, files in os.walk(build_dir):
            for fn in files:
                if fn.endswith(".sh") or fn in ("configure", "config.sub", "config.guess", "version.sh"):
                    fp = os.path.join(root, fn)
                    try:
                        st = os.stat(fp)
                        os.chmod(fp, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    except Exception:
                        pass
        info(f"[LFS-STRIP build_arch] build_dir={build_dir}")
        with current_directory(self.get_build_dir(arch.arch)):
            env = self.get_recipe_env(arch)
            configure = sh.Command('./configure')
            shprint(configure,
                    f'--host={arch.command_prefix}',
                    '--disable-asm',
                    '--disable-cli',
                    '--enable-pic',
                    '--enable-static',
                    '--prefix={}'.format(realpath('.')),
                    _env=env)
            info(f"[LFS-STRIP build_arch] configure done, now stripping")
            self._strip_lfs_macros(build_dir)
            info(f"[LFS-STRIP build_arch] strip done, now make")
            shprint(sh.make, '-j', str(cpu_count()), _env=env)
            shprint(sh.make, 'install', _env=env)

recipe = LibX264Recipe()
