#!/usr/bin/env python3
"""Setup script."""
import logging
import os
import subprocess  # noqa S404  # nosec: B404
import sys

from setuptools import setup
from setuptools.command.build_py import build_py


class Build(build_py):
    """Install npm packages."""

    def run(self):
        """Npm install commands."""
        npm_packages = [r.strip() for r in open_file("requirements_npm.txt") if not r.startswith("#")]
        logging.warning(f"Installing the following npm packages {npm_packages}")

        current_dir = os.getcwd()
        node_module_dir = os.path.join(sys.prefix, "bin", "node_modules")
        os.makedirs(node_module_dir, exist_ok=True)
        os.chdir(node_module_dir)

        for package in npm_packages:
            logging.warning(f"Running command npm install {package}")
            result = subprocess.run(
                ["npm", "install", package], stderr=subprocess.PIPE
            )  # noqa: S603  # nosec: B603 B607
            if result.returncode != 0:
                logging.warning(f"Failed to run command 'npm {package}' with error {result.stderr.decode()}")
                sys.exit(-1)

        os.chdir(current_dir)
        build_py.run(self)


def open_file(fname):
    """Open and return a file-like object for the relative filename."""
    return open(os.path.join(os.path.dirname(__file__), fname))


setup(
    name="azul-plugin-js-deobf",
    description="Deobfuscates JavaScript to make it more human readable.",
    cmdclass={"build_py": Build},
    author="Azul",
    author_email="azul@asd.gov.au",
    url="https://www.asd.gov.au/",
    packages=["azul_plugin_js_deobf"],
    include_package_data=True,
    python_requires=">=3.12",
    classifiers=[],
    entry_points={
        "console_scripts": [
            "azul-plugin-js-deobf = azul_plugin_js_deobf.main:main",
        ]
    },
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    install_requires=[r.strip() for r in open_file("requirements.txt") if not r.startswith("#")],
)
