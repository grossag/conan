from conan.errors import ConanException
from conan.tools.build import cmd_args_to_string


def msbuild_verbosity_cmd_line_arg(conanfile):
    """
    Controls msbuild verbosity.
    See https://learn.microsoft.com/en-us/visualstudio/msbuild/msbuild-command-line-reference
    :return:
    """
    verbosity = conanfile.conf.get("tools.build:verbosity", choices=("quiet", "verbose"))
    if verbosity is not None:
        verbosity = {
            "quiet": "Quiet",
            "verbose": "Detailed",
        }.get(verbosity)
        return f'/verbosity:{verbosity}'
    return ""


def msbuild_arch(arch):
    return {'x86': 'x86',
            'x86_64': 'x64',
            'armv7': 'ARM',
            'armv8': 'ARM64',
            'arm64ec': 'ARM64EC'}.get(str(arch))


class MSBuild(object):
    """
    MSBuild build helper class
    """

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile
        #: Defines the build type. By default, ``settings.build_type``.
        self.build_type = conanfile.settings.get_safe("build_type")
        # if platforms:
        #    msvc_arch.update(platforms)
        arch = conanfile.settings.get_safe("arch")
        msvc_arch = msbuild_arch(arch)
        if conanfile.settings.get_safe("os") == "WindowsCE":
            msvc_arch = conanfile.settings.get_safe("os.platform")
        #: Defines the platform name, e.g., ``ARM`` if ``settings.arch == "armv7"``.
        self.platform = msvc_arch

    def command(self, sln, targets=None):
        """
        Gets the ``msbuild`` command line. For instance,
        :command:`msbuild "MyProject.sln" /p:Configuration=<conf> /p:Platform=<platform>`.

        :param sln: ``str`` name of Visual Studio ``*.sln`` file
        :param targets: ``targets`` is an optional argument, defaults to ``None``, and otherwise it is a list of targets to build
        :return: ``str`` msbuild command line.
        """
        cmd = ["msbuild", sln,
               f"/p:Configuration={self.build_type}",
               f"/p:Platform={self.platform}"]

        verbosity = msbuild_verbosity_cmd_line_arg(self._conanfile)
        if verbosity:
            cmd.append(verbosity)

        maxcpucount = self._conanfile.conf.get("tools.microsoft.msbuild:max_cpu_count",
                                               check_type=int)
        if maxcpucount:
            cmd.append("/m:{}".format(maxcpucount))
        else:
            cmd.append("/m") # Allow parallel build, without a max cpu count

        if targets:
            if not isinstance(targets, list):
                raise ConanException("targets argument should be a list")
            cmd.append("/target:{}".format(";".join(targets)))

        cmd += self._conanfile.conf.get("tools.microsoft.msbuild:flags",
                                        default=[], check_type=list)
        return cmd_args_to_string(cmd)

    def build(self, sln, targets=None):
        """
        Runs the ``msbuild`` command line obtained from ``self.command(sln)``.

        :param sln: ``str`` name of Visual Studio ``*.sln`` file
        :param targets: ``targets`` is an optional argument, defaults to ``None``, and otherwise it is a list of targets to build
        """
        cmd = self.command(sln, targets=targets)
        self._conanfile.run(cmd)

    @staticmethod
    def get_version(_):
        return NotImplementedError("get_version() method is not supported in MSBuild "
                                   "toolchain helper")
