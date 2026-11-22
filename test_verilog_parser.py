import unittest

from verilog_parser import generate_testbench_skeleton


def make_module(instantiations=None, ports=None):
    return {
        "module_name": "Top",
        "ports": ports or [
            {"name": "a", "direction": "input", "bits": 1, "width_msb": None, "width_lsb": None},
            {"name": "y", "direction": "output", "bits": 1, "width_msb": None, "width_lsb": None},
        ],
        "instantiations": instantiations or [],
        "params": {},
    }


class TestbenchGenerationTests(unittest.TestCase):
    def test_new_testbench_uses_display_after_each_vector_and_never_monitor(self):
        tb = generate_testbench_skeleton(make_module())

        self.assertNotIn("$monitor", tb)
        self.assertIn("#10;", tb)
        self.assertIn('$display("a=%b | y=%b", a, y);', tb)
        self.assertIn("for (i = 0; i < (1 << 1); i = i + 1)", tb)
        self.assertIn("#10; $display", tb)

    def test_gate_delay_testbench_uses_settling_delay(self):
        module = make_module(instantiations=[
            {"is_primitive": False, "params": {}},
        ])
        tb = generate_testbench_skeleton(module)

        self.assertNotIn("$monitor", tb)
        self.assertIn("#100;", tb)
        self.assertIn("#100; $display", tb)
        self.assertIn("settled values only", tb)

    def test_self_checking_testbench_keeps_pass_fail_output_without_monitor(self):
        tb = generate_testbench_skeleton(
            make_module(),
            checks={"y": "a"},
        )

        self.assertNotIn("$monitor", tb)
        self.assertIn("PASS:", tb)
        self.assertIn("FAIL:", tb)


if __name__ == "__main__":
    unittest.main()
