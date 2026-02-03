"""Install npm packages at install time."""

# hatch_build.py
import logging
import os
import subprocess
import sys

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Install npm packages at install time."""

    def initialize(self, version, build_data):
        """Install npm packages at install time."""
        with open("requirements_npm.txt") as f:
            npm_packages = [r.strip() for r in f.readlines() if not r.startswith("#")]
        logging.warning(f"Installing the following npm packages {npm_packages}")

        current_dir = os.getcwd()
        node_module_dir = os.path.join(sys.base_prefix, "bin", "node_modules")
        os.makedirs(node_module_dir, exist_ok=True)
        os.chdir(node_module_dir)

        for package in npm_packages:
            logging.warning(f"Running command npm install {package}")
            result = subprocess.run(["npm", "install", package], stderr=subprocess.PIPE)  # noqa: S603, S607
            if result.returncode != 0:
                logging.warning(f"Failed to run command 'npm {package}' with error {result.stderr.decode()}")
                sys.exit(-1)
        os.chdir(current_dir)
