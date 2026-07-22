from os.path import exists, join
from multiprocessing import cpu_count
from pathlib import Path
from pythonforandroid.recipe import Recipe
from pythonforandroid.logger import shprint
from pythonforandroid.util import current_directory
import sh


class LibffiRecipe(Recipe):
    """
    Requires additional system dependencies on Ubuntu:
        - `automake` for the `aclocal` binary
        - `autoconf` for the `autoreconf` binary
        - `libltdl-dev` which defines the `LT_SYS_SYMBOL_USCORE` macro
    """
    name = 'libffi'
    version = 'v3.4.2'
    url = 'https://github.com/libffi/libffi/archive/{version}.tar.gz'

    patches = ['remove-version-info.patch']

    built_libraries = {'libffi.so': '.libs'}

    def get_recipe_env(self, arch):
        # Strip TARGET_FLAGS from env CFLAGS so configure --host= is the
        # ONLY place that sets -target. Duplicated -target resets the NDK
        # r28c toolchain mid-invocation and breaks linking (p4a#3298 class).
        env = super().get_recipe_env(arch)
        tflags = f'-target {arch.command_prefix}'
        for var in ('CFLAGS', 'CXXFLAGS', 'CPPFLAGS'):
            env[var] = env[var].replace(tflags, '')
        return env

    def build_arch(self, arch):
        env = self.get_recipe_env(arch)
        build_dir = self.get_build_dir(arch.arch)
        # Insert #include <string.h> into every ffi.c so NDK r28c clang
        # doesn't error on implicit memcpy (conftest passes but real build
        # uses -Werror-equivalent strictness).
        for f in Path(build_dir).rglob('ffi.c'):
            t = f.read_text()
            if '#include <string.h>' not in t:
                t = t.replace('#include "ffi_common.h"',
                              '#include <string.h>\n#include "ffi_common.h"')
                f.write_text(t)
        with current_directory(build_dir):
            if not exists('configure'):
                shprint(sh.Command('./autogen.sh'), _env=env)
            shprint(sh.Command('autoreconf'), '-vif', _env=env)
            shprint(sh.Command('./configure'),
                    '--host=' + arch.command_prefix,
                    '--prefix=' + build_dir,
                    '--disable-builddir',
                    '--enable-shared', _env=env)
            shprint(sh.make, '-j', str(cpu_count()), 'libffi.la', _env=env)

    def get_include_dirs(self, arch):
        return [join(self.get_build_dir(arch), 'include')]


recipe = LibffiRecipe()
