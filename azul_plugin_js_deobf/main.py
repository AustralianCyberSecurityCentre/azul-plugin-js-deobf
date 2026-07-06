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

    VERSION = "2026.07.06v2"
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

    def is_file_valid(self, fileObj: tempfile._TemporaryFileWrapper) -> bool:
        """Check deobfuscated file has at least one newline, and has content. Return false if it doesn't."""
        # If the first line is longer than 10kb it's probably not useful anyway.
        # Note the number parameter in readlines() is the number of bytes before the code stops searching for newlines.
        file_data = fileObj.readlines(10_000)
        fileObj.seek(0)

        num_lines = len(file_data)
        if num_lines == 1:
            return False, "single line file"

        file_bytes = len(file_data[0])
        if file_bytes == 0:
            return False, "0 file length"

        return True, None

    def get_bracket_hash(self, file) -> str:
        """Using a regular expression, determine the bracket layout of a file."""
        # Return the md5 hash of it if possible.
        # Otherwise return false.
        try:
            bracket_structure = "".join(re.findall(r"[{}\[\]()]", str(file)))
            if bracket_structure == "":
                return False
            else:
                md5_hash = hashlib.md5((bracket_structure).encode("utf-8")).hexdigest()  # noqa: S324
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
            minified_hash = hashlib.md5((str(minified)).encode("utf-8")).hexdigest()  # noqa: S324
            if minified_hash:
                self.add_feature_values("js_minified_hash", str(minified_hash))
        except Exception as e:
            self.logger.warning(f"Error while finding js_minified_hash: {e}")

        # Check if the npm binaries are present and locate their path
        # Path is actually found from node_modules/.bin/webcrack but that is a symlink which breaks in python pkg.
        webcrack_path = find_executable(
            os.path.join(self.node_module_path, "webcrack", "src", "cli-wrapper.js"),
            extra_paths=".",
        )
        if not os.path.exists(webcrack_path):
            raise Exception(f"Webcrack cannot be found at the path {webcrack_path}")

        with tempfile.NamedTemporaryFile("rb") as webcrack_file:
            result = subprocess.run(  # noqa: S603
                [webcrack_path, src_file],
                stdout=webcrack_file,
                stderr=subprocess.PIPE,
            )
            webcrack_file.seek(0)

            # try rerun without JSX if theres an errror - only testing for now
            if b"JSX" in result.stderr and result.returncode != 0:
                result = subprocess.run(  # noqa: S603
                    [webcrack_path, src_file, "--no-jsx"],
                    stdout=webcrack_file,
                    stderr=subprocess.PIPE,
                )
                webcrack_file.seek(0)

            if result.returncode != 0:
                decoded_err = result.stderr.decode("utf-8")

                if "SyntaxError: " in decoded_err:
                    return State(
                        State.Label.OPT_OUT,
                        message="Not a Javascript file, opting out.",
                    )

                if "JavaScript heap out of memory" in decoded_err:
                    return State(
                        State.Label.ERROR_RUNNER,
                        message="Ran out of memory.",
                    )

                # Handle new errors here as they appear
                return State(
                    State.Label.ERROR_RUNNER,
                    message=f"Failed with error:\n{decoded_err}",
                )

            file_valid = self.is_file_valid(webcrack_file)
            if not file_valid[0]:
                self.logger.warning(f"Webcracker output failed validation: {file_valid[1]}.")
                return

            self._add_js_file(webcrack_file, "Webcrack")


def main():
    """Plugin command-line entrypoint."""
    cmdline_run(plugin=AzulPluginJsDeobf)


if __name__ == "__main__":
    main()
