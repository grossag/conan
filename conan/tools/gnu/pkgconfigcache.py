from conan.errors import ConanException
from conan.tools.files import mkdir, save, load, rmdir
from conan.tools.gnu.pkgconfig import PkgConfig
from conans.model.build_info import CppInfo

from io import StringIO
import glob
import yaml
import os

class PkgConfigCache:
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._components = {}

    @property
    def _conan_prefix(self):
        return "CONAN_PACKAGE_FOLDER"

    @property
    def _cache_file_path(self):
        return os.path.join(self._conanfile.package_folder, "res", "pkg_config_cache.yml")

    def add_file(self, path, use_mod_version=False):
        cpp_info = CppInfo()
        pkg_config = PkgConfig(self._conanfile, path,
                               pkg_config_path=[
                                  self._conanfile.generators_folder, # To find PkgConfigDeps generated .pc files for our dependencies
                                  os.path.dirname(path), # To find any other .pc files from this package
                               ],
                               prefix=self._conan_prefix)
        pkg_config.fill_cpp_info(cpp_info)

        filename = os.path.basename(path)[:-3]
        cpp_info.set_property("pkg_config_name",  filename)
        if use_mod_version:
            cpp_info.set_property("component_version", pkg_config.version)

        # Filter common variables which we do not care about, we only want
        # the unusual variables which may be used by consumers. e.g. xcb sets
        # xcbincludedir.
        #
        # The common variables like includedir are merely variables used to
        # populate Cflags: -I{includedir}... and we get those values using
        # pkg-config --cflags-only-I
        variables = pkg_config.variables
        for k in ["prefix", "exec_prefix", "pcfiledir", "includedir", "libdir"]:
            variables.pop(k, None)

        # Include non-standard variables as pkg_config_custom_content which is
        # written to the output .pc file
        pkg_config_custom_content = ""
        for variable, value in variables.items():
            value = value.replace(self._conan_prefix, "${prefix}/")
            pkg_config_custom_content += f"{variable}={value}\n"

        if pkg_config_custom_content:
            cpp_info.set_property("pkg_config_custom_content", pkg_config_custom_content)

        self._components[filename] = cpp_info.serialize()

    def add_folder(self, path, use_mod_version=False):
        found = False
        for fn in glob.glob(os.path.join(path, "*.pc")):
            self.add_file(fn)
            found = True
        if not found:
            raise ConanException("PkgConfigCache error, no .pc files found in '{}'".format(path))
        rmdir(self._conanfile, path)

    def install(self):
        cache_file_path = self._cache_file_path
        mkdir(self, os.path.dirname(cache_file_path))
        save(self, cache_file_path, yaml.dump(self._components))

    def load(self):
        yaml_data = load(self._conanfile, self._cache_file_path)
        yaml_data = yaml_data.replace(self._conan_prefix, self._conanfile.package_folder)
        self._components = yaml.safe_load(yaml_data)

    def fill_cpp_info(self):
        if not self._components:
            self.load()
        if len(self._components.items()) == 1:
            # When there is only one pkg-config file then we do not need components
            serialized_cpp_info = next(iter(self._components.values()))
            self._conanfile.cpp_info = CppInfo(set_defaults=False).deserialize(serialized_cpp_info)
        else:
            for filename, serialized_cpp_info in self._components.items():
                self._conanfile.cpp_info.components[filename] = CppInfo(set_defaults=False).deserialize(serialized_cpp_info)
