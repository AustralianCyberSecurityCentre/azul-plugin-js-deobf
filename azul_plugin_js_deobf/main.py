"""Deobfuscates JavaScript to make it more human readable."""

# Azul 2 imports for JS plugin
import hashlib
import os
import re
import subprocess  # nosec B404
import tempfile

import rjsmin
from azul_runner import (
    BinaryPlugin,
    DataLabel,
    Feature,
    FeatureType,
    Job,
    State,
    add_settings,
    cmdline_run,
)


def find_executable(name, extra_paths=None):
    """Return full path to requested executable."""
    paths = list(os.environ["PATH"].split(os.pathsep))
    if extra_paths:
        paths.extend(extra_paths)
    for p in paths:
        f = os.path.join(p, name)
        if os.path.isfile(f):
            return f
    raise BadNpmPackagePath("Npm package '{}' not found in path: {}".format(name, paths))


class BadNpmPackagePath(Exception):
    """Error raised if an npm executable's path can't be found."""

    pass


class AzulPluginJsDeobf(BinaryPlugin):
    """Deobfuscates JavaScript to make it more human readable."""

    VERSION = "2025.10.01"
    SETTINGS = add_settings(
        filter_max_content_size=(int, 10 * 1024 * 1024),  # File size to process
        run_timeout=(int, 60 * 5),  # sometimes this takes a long time.
        filter_data_types={"content": ["code/javascript", "code/jscript"]},
    )

    FEATURES = [
        Feature("js_bracket_hash", desc="MD5 of the bracket structure of the JavaScript", type=FeatureType.String),
        Feature(
            "js_minified_hash",
            desc="MD5 of JavaScript after being minified",
            type=FeatureType.String,
        ),
    ]

    node_module_path = os.path.join("node_modules")

    def _add_js_file(self, file_ref: tempfile._TemporaryFileWrapper, deob_tool_name: str) -> bool:
        """Add a child binary and if there are any issues log a warning."""
        if os.stat(file_ref.name).st_size == 0:
            self.logger.warning(
                f"The tool {deob_tool_name} failed to add a child binary because the output file has no contents."
            )
            return False

        file_ref.seek(0)
        self.add_data_file(DataLabel.DEOB_JS, {}, file_ref)

    def is_file_got_multiplelines(self, fileObj: tempfile._TemporaryFileWrapper) -> bool:
        """Check deobfuscated file has at least one newline and return false if it doesn't."""
        # If the first line is longer than 10kb it's probably not useful anyway.
        # Note the number parameter in readlines() is the number of bytes before the code stops searching for newlines.
        num_lines = len(fileObj.readlines(10000))
        fileObj.seek(0)
        if num_lines == 1:
            return False
        return True

    def get_bracket_hash(self, file) -> str:
        """Using a regular expression, determine the bracket layout of a file."""
        # Return the md5 hash of it if possible.
        # Otherwise return false.
        try:
            bracket_structure = "".join(re.findall(r"[{}\[\]()]", str(file)))
            if bracket_structure == "":
                return False
            else:
                md5_hash = hashlib.md5((bracket_structure).encode("utf-8")).hexdigest()  # nosec B324
                return str(md5_hash)
        except Exception:
            return False

    def execute(self, job: Job):
        """Run the plugin."""
        src_file = job.get_data().get_filepath()
        text = job.get_data().read()
        # Parsing js file and attempting to return features.
        # note: rjsmin will 'minify' any string, stream of bytes, etc.
        # therefore, it is relying on the plugin settings to filter for JavaScript files.
        try:
            minified = rjsmin.jsmin(text)
            bracket_hash = self.get_bracket_hash(str(minified))
            if bracket_hash:
                self.add_feature_values("js_bracket_hash", str(bracket_hash))

        except Exception as e:
            self.logger.warning(f"Error while finding js_bracket_hash: {e}")

        try:
            minified = rjsmin.jsmin(text)
            minified_hash = hashlib.md5((str(minified)).encode("utf-8")).hexdigest()  # nosec B324
            if minified_hash:
                self.add_feature_values("js_minified_hash", str(minified_hash))
        except Exception as e:
            self.logger.warning(f"Error while finding js_minified_hash: {e}")

        # Check if the npm binaries are present and locate their path
        # Path is actually found from node_modules/.bin/synchrony but that is a symlink which breaks in python pkg.
        synchrony_path = find_executable(
            os.path.join(self.node_module_path, "deobfuscator", "dist", "cli.js"), extra_paths="."
        )
        if not os.path.exists(synchrony_path):
            raise Exception(f"Synchrony cannot be found at the path {synchrony_path}")
        # Path is actually found from node_modules/.bin/restringer but that is a symlink which breaks in python pkg.
        restringer_path = find_executable(
            os.path.join(self.node_module_path, "restringer", "bin", "deobfuscate.js"), extra_paths="."
        )
        if not os.path.exists(restringer_path):
            raise Exception(f"Restringer cannot be found at the path {restringer_path}")

        # Start processing.
        with tempfile.NamedTemporaryFile("rb") as sync_file:
            result_sync = subprocess.run(
                [synchrony_path, src_file, "-o", sync_file.name],
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
            )  # nosec B603

            if result_sync.returncode != 0:
                decoded_std_err = result_sync.stderr.decode()
                if "SyntaxError:" in decoded_std_err:
                    return State(State.Label.OPT_OUT, message="Not a Javascript file opting out.")
                # Failure case when there is too much recursion in the synchrony library.
                if "RangeError: Maximum call stack size exceeded" in decoded_std_err:
                    return State(
                        State.Label.COMPLETED_WITH_ERRORS,
                        failure_name="Synchrony failed too much recursion",
                        message=decoded_std_err,
                    )

            with tempfile.NamedTemporaryFile("rb") as restring_file:
                result_restring = subprocess.run(
                    [restringer_path, sync_file.name, "-o", restring_file.name],
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                )  # nosec B603

                # If restringer failed return the synchrony result
                # Restringer can fail and return a code of 0 but have an output file of size 0 and stdout has the error
                # This is why the file length is checked.
                if result_restring.returncode != 0 or os.stat(restring_file.name).st_size == 0:
                    self.logger.warning(
                        f"Restringer failed, using synchrony output, stderr is: '{result_restring.stderr.decode()}'"
                        + f"\nstdout is: {result_restring.stdout.decode()}"
                    )
                    if self.is_file_got_multiplelines(sync_file):
                        self._add_js_file(sync_file, "Synchrony")
                    return
                if self.is_file_got_multiplelines(restring_file):
                    self._add_js_file(restring_file, "Restringer")


def main():
    """Plugin command-line entrypoint."""
    cmdline_run(plugin=AzulPluginJsDeobf)


if __name__ == "__main__":
    main()
