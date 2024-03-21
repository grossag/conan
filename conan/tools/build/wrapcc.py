import os
import textwrap

from conans.util.files import save
from conan.tools.build import cmd_args_to_string

def _chmod_plus_x(filename):
    if os.name == "posix":
        os.chmod(filename, os.stat(filename).st_mode | 0o111)


def _take_sysroot_flags(flags):
    sysroot_flags = [f for f in flags if f.startswith('--sysroot=')]
    remaining_flags = [f for f in flags if f not in sysroot_flags]
    return (sysroot_flags, remaining_flags)


def _take_binutils_flags(flags):
    indices = [i for i in range(len(flags)) if flags[i] == '-B']
    binutil_flags = [flags[i] for i in range(len(flags)) if (i in indices or (i - 1) in indices)]
    remaining_flags = [flags[i] for i in range(len(flags)) if (i not in indices and (i - 1) not in indices)]
    return (binutil_flags, remaining_flags)


def generate_wrapcc(conanfile, wrap_cc_filename, cc, cflags):
    """
    Generate a wrapper .sh to call compiler with --sysroot and -B flags inlined,
    this is due to some build systems not passing sysroot when we need it to.

    Returns: (path_to_wrap_cc, remaining_cflags)
       path_to_wrap_cc may be None if a wrapper was not required
    """

    if conanfile.settings.compiler != "gcc":
        # Currently only GCC is supported with wrapcc
        return (None, cflags)

    # Look for cflags --sysroot from glibc and -B from binutils
    sysroot_flags, remaining_flags = _take_sysroot_flags(cflags)
    binutils_flags, remaining_flags = _take_binutils_flags(remaining_flags)
    arch_flags = []

    # When cross-compiling for x86 from x86_64 we must specify -m32
    if conanfile.settings_build.get_safe('arch') == 'x86_64' and conanfile.settings.get_safe("arch") == 'x86':
        arch_flags.append('-m32')

    wrap_flags = cmd_args_to_string(sysroot_flags + binutils_flags + arch_flags)
    if not wrap_flags:
        # If we have no flags, we do not need to generate a wrapper
        return (None, cflags)

    # Generate wrapper with flags inlined
    wrap_cc = os.path.abspath(wrap_cc_filename)
    save(wrap_cc, textwrap.dedent("""\
        #!/usr/bin/env bash
        exec %s %s $@
    """ % (cc, wrap_flags)))
    _chmod_plus_x(wrap_cc)

    return (wrap_cc, remaining_flags)
