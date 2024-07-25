from io import StringIO

from conan.tools.apple.apple import is_apple_os
from conan.tools.build import cmd_args_to_string
from conan.tools.env import Environment
from conan.errors import ConanException


class PkgConfig:

    def __init__(self, conanfile, library, pkg_config_path=None, prefix=None, no_recursive=False):
        """

        :param conanfile: The current recipe object. Always use ``self``.
        :param library: The library which ``.pc`` file is to be parsed. It must exist in the pkg_config path.
        :param pkg_config_path:  If defined it will be prepended to ``PKG_CONFIG_PATH`` environment
               variable, so the execution finds the required files.
        """
        self._conanfile = conanfile
        self._library = library
        self._info = {}
        self._pkg_config_path = pkg_config_path
        self._prefix = prefix
        self._variables = None
        self._no_recursive = no_recursive

    def _parse_output(self, option):
        executable = self._conanfile.conf.get("tools.gnu:pkg_config", default="pkg-config")
        command = [executable, '--' + option, self._library, '--print-errors']
        if self._no_recursive:
            command += ["--maximum-traverse-depth=1"]
        if self._prefix:
            command += ["--define-variable=prefix=%s" % self._prefix]
        command = cmd_args_to_string(command)

        env = Environment()
        env.define("PKG_CONFIG_SYSROOT_DIR", "")
        if self._pkg_config_path:
            env.prepend_path("PKG_CONFIG_PATH", self._pkg_config_path)
        with env.vars(self._conanfile).apply():
            # This way we get the environment from ConanFile, from profile (default buildenv)
            output = StringIO()
            self._conanfile.run(command, stdout=output, quiet=True)
        value = output.getvalue().strip()
        return value

    def _get_option(self, option):
        if option not in self._info:
            self._info[option] = self._parse_output(option)
        return self._info[option]

    @property
    def includedirs(self):
        return [include[2:] for include in self._get_option('cflags-only-I').split()]

    @property
    def cflags(self):
        return [flag for flag in self._get_option('cflags-only-other').split()
                if not flag.startswith("-D")]

    @property
    def defines(self):
        return [flag[2:] for flag in self._get_option('cflags-only-other').split()
                if flag.startswith("-D")]

    @property
    def libdirs(self):
        return [lib[2:] for lib in self._get_option('libs-only-L').split()]

    @property
    def libs(self):
        return [lib[2:] for lib in self._get_option('libs-only-l').split()]

    @property
    def linkflags(self):
        return self._get_option('libs-only-other').split()

    @property
    def provides(self):
        return self._get_option('print-provides')

    @property
    def version(self):
        return self._get_option('modversion')

    @property
    def requires(self):
        return [lib.split()[0] for lib in self._get_option('print-requires').splitlines()]

    @property
    def requires_private(self):
        return [lib.split()[0] for lib in self._get_option('print-requires-private').splitlines()]

    @property
    def variables(self):
        if self._variables is None:
            variable_names = self._parse_output('print-variables').split()
            self._variables = {}
            for name in variable_names:
                self._variables[name] = self._parse_output('variable=%s' % name)
        return self._variables

    def fill_cpp_info(self, cpp_info, is_system=True, system_libs=None):
        """
        Method to fill a cpp_info object from the PkgConfig configuration

        :param cpp_info: Can be the global one (self.cpp_info) or a component one (self.components["foo"].cpp_info).
        :param is_system: If ``True``, all detected libraries will be assigned to ``cpp_info.system_libs``, and none to ``cpp_info.libs``.
        :param system_libs: If ``True``, all detected libraries will be assigned to ``cpp_info.system_libs``, and none to ``cpp_info.libs``.

        """
        if not self.provides:
            raise ConanException("PkgConfig error, '{}' files not available".format(self._library))
        self._conanfile.output.verbose(f"PkgConfig fill cpp_info for {self._library}")
        if is_system:
            cpp_info.system_libs = self.libs
        else:
            system_libs = system_libs or []
            cpp_info.libs = [lib for lib in self.libs if lib not in system_libs]
            cpp_info.system_libs = [lib for lib in self.libs if lib in system_libs]
        cpp_info.libdirs = self.libdirs
        if is_apple_os(self._conanfile):
            linkflags = []
            frameworks = []
            is_framework = False
            for linkflag in self.linkflags:
                if is_framework:
                    frameworks.append(linkflag)
                    is_framework = False
                elif '-framework' == linkflag.strip():
                    is_framework = True
                else:
                    linkflags.append(linkflag)
            cpp_info.sharedlinkflags = linkflags
            cpp_info.exelinkflags = linkflags
            cpp_info.frameworks = frameworks
        else:
            cpp_info.sharedlinkflags = self.linkflags
            cpp_info.exelinkflags = self.linkflags
        cpp_info.defines = self.defines
        cpp_info.includedirs = self.includedirs
        cpp_info.cflags = self.cflags
        cpp_info.cxxflags = self.cflags

        # The order of requires and requires_private make sense for linker
        # on Linux, so we need to keep it in cpp_info
        pc_conan_map = {}
        for dependency in self._conanfile.dependencies.host.values():
            pkg_config_name = dependency.cpp_info.get_property("pkg_config_name")
            pc_conan_map[pkg_config_name] = "%s::%s" % (dependency.ref.name, dependency.ref.name)

            for component_name, component in dependency.cpp_info.components.items():
                component_pkg_config_name = component.get_property("pkg_config_name")
                pc_conan_map[component_pkg_config_name] = "%s::%s" % (dependency.ref.name, component_name)

        for dst, src in [(cpp_info.requires, self.requires), (cpp_info.requires_private, self.requires_private)]:
            for require in src:
                # From the list of Requires in the .pc file, map them to conan dependencies
                # and their components
                dst.append(pc_conan_map.get(require, require))
