"""Test cases for plugin output."""

import datetime

from azul_runner import FV, DataLabel, Event, EventData, JobResult, State, test_template

from azul_plugin_js_deobf.main import AzulPluginJsDeobf


class TestExecute(test_template.TestPlugin):
    PLUGIN_TO_TEST = AzulPluginJsDeobf

    def test_fail(self):
        """Test a run where an error status is raised"""
        data = self.load_test_file_bytes(
            "702e31ed1537c279459a255460f12f0f2863f973e121cd9194957f4f3e7b0994",
            "Benign WIN32 EXE, python library executable python_mcp.exe",
        )
        result = self.do_execution(
            ent_id="not_a_test_entity_to_allow_type_override",
            entity_attrs={"file_format": "text/plain"},
            data_in=[("content", data)],
            verify_input_content=False,
        )
        self.assertJobResult(
            result,
            JobResult(state=State(State.Label.OPT_OUT, message="Not a Javascript file opting out.")),
        )

    def test_execute(self):
        """Test can deobfuscate basic minified javascript."""
        data = self.load_cart(
            "87ffc6e3cb934d89de29637321a82ff898652858aebea9620ce59cb7252790dd.cart",
            description="minified JS created by Azul team.",
        )
        result = self.do_execution(data_in=[("content", data)])
        self.assertJobResult(
            result,
            JobResult(
                state=State(State.Label.COMPLETED),
                events=[
                    Event(
                        sha256="87ffc6e3cb934d89de29637321a82ff898652858aebea9620ce59cb7252790dd",
                        data=[EventData(hash="0", label="deob_js")],
                        features={
                            "js_bracket_hash": [FV("4f22246fc4d7f685c8eddf7858002caa")],
                            "js_minified_hash": [FV("423baf06a97b236f063b4493384942a8")],
                        },
                    )
                ],
                data={"0": b""},
            ),
            strip_hash=True,
        )

    def test_syntax_error_opt_out(self):
        """Test can fail gracefully on non-js text files."""
        data = self.load_test_file_bytes(
            "d971eeb4926f49ca325409aeb6fe5d1b458fe88224f14d649203800520abc763", "Benign Javascript file."
        )
        result = self.do_execution(data_in=[("content", data)], verify_input_content=False)
        self.assertJobResult(
            result,
            JobResult(state=State(State.Label.OPT_OUT, message="Not a Javascript file opting out.")),
        )

    def test_restringer_fails_to_deob(self):
        """Test can have synchrony generate output and resync fail and still get output."""
        data = self.load_test_file_bytes(
            "dd8c1108346f4d27e092ce03cafcf7ef8ae743214430ed00906dcb8f88496a79", "Javascript that breaks resync."
        )
        result = self.do_execution(data_in=[("content", data)])
        self.assertJobResult(
            result,
            JobResult(
                state=State(State.Label.COMPLETED),
                events=[
                    Event(
                        sha256="dd8c1108346f4d27e092ce03cafcf7ef8ae743214430ed00906dcb8f88496a79",
                        data=[EventData(hash="0", label="deob_js")],
                        features={
                            "js_bracket_hash": [FV("c4097a7294c6f1c460b5b220df0d3ada")],
                            "js_minified_hash": [FV("0b353d7ecb8774095755b2069ea4b3ac")],
                        },
                    )
                ],
                data={"0": b""},
            ),
            strip_hash=True,
        )

    def test_disacard_garbage_output(self):
        """Test a text file filled with hex, output should be discarded."""
        data = self.load_cart(
            "a0b388ed6a51cd1914e95c6d6c787e3a868f2a02b7107f8a7bf3713432affeb9.cart",
            description="Text file filled with HEX created by Azul team.",
        )
        result = self.do_execution(data_in=[("content", data)], verify_input_content=False)
        self.assertJobResult(
            result,
            JobResult(
                state=State(State.Label.COMPLETED),
                events=[
                    Event(
                        sha256="a0b388ed6a51cd1914e95c6d6c787e3a868f2a02b7107f8a7bf3713432affeb9",
                        features={"js_minified_hash": [FV("55686de0f46b9f860190e64a10b026e8")]},
                    )
                ],
            ),
        )

    def test_fails_with_attrib_error(self):
        """Test failure due to attributeError regression test."""
        data = self.load_test_file_bytes(
            "ef73f10d5163ea12ee4ff5507ebc387591dd1d97fc9a1a143cf58c14793dd371",
            "Malicious Javascript, malware family kriptick.",
        )
        result = self.do_execution(data_in=[("content", data)])
        # Ignore message because it's a huge stacktrace.
        result.state.message = None
        self.assertJobResult(
            result,
            JobResult(
                state=State(State.Label.COMPLETED_WITH_ERRORS, failure_name="Synchrony failed too much recursion"),
                events=[
                    Event(
                        sha256="ef73f10d5163ea12ee4ff5507ebc387591dd1d97fc9a1a143cf58c14793dd371",
                        features={
                            "js_bracket_hash": [FV("f33267b039aa3c3e9c3783c5d19a4dd3")],
                            "js_minified_hash": [FV("8bef9bdff8dc321a73e6d77a8c516252")],
                        },
                    )
                ],
            ),
        )

    def test_bracket_hash(self):
        """Test resulting features from generic js file"""
        data = self.load_test_file_bytes(
            "ecb916133a9376911f10bc5c659952eb0031e457f5df367cde560edbfba38fb8",
            "jquery.js",
        )
        result = self.do_execution(data_in=[("content", data)])
        result.state.message = None
        self.assertJobResult(
            result,
            JobResult(
                state=State(State.Label.COMPLETED),
                events=[
                    Event(
                        sha256="ecb916133a9376911f10bc5c659952eb0031e457f5df367cde560edbfba38fb8",
                        data=[
                            EventData(
                                hash="e847c61ce65de33fe33c87913767deb29cda09e44bfdce3a617db68ec20c879c",
                                label="deob_js",
                            )
                        ],
                        features={
                            "js_bracket_hash": [FV("97091e99f28f041fb4e1abb8fd61524a")],
                            "js_minified_hash": [FV("8d4ab4cf851e65a253d4c4a52465931f")],
                        },
                    )
                ],
                data={"e847c61ce65de33fe33c87913767deb29cda09e44bfdce3a617db68ec20c879c": b""},
            ),
        )
