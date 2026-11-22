import unittest
import tempfile
from pathlib import Path

from verilog_parser import generate_testbench_skeleton, scan_module_dir
from welcome import create_module_files


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
        self.assertIn("#100;", tb)
        self.assertIn('$display("a=%b | y=%b", a, y);', tb)
        self.assertIn("for (i = 0; i < (1 << 1); i = i + 1)", tb)
        self.assertIn("#100; $display", tb)

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


class ModuleFolderTests(unittest.TestCase):
    def test_module_and_testbench_are_created_in_module_named_folder(self):
        with tempfile.TemporaryDirectory() as td:
            made = create_module_files(Path(td), "Adder", inputs="a, b", outputs="sum")

            folder = Path(td) / "Adder"
            self.assertEqual([p.parent for p in made], [folder, folder])
            self.assertEqual([p.name for p in made], ["Adder.v", "Adder_tb.v"])
            self.assertTrue((folder / "Adder.v").is_file())
            self.assertTrue((folder / "Adder_tb.v").is_file())

    def test_workspace_scans_modules_in_nested_folders(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Training" / "Adder"
            folder.mkdir(parents=True)
            (folder / "Adder.v").write_text("module Adder(input a, output y); assign y = a; endmodule\n")

            modules = scan_module_dir(Path(td) / "Training")

            self.assertIn("Adder", modules)
            self.assertEqual(modules["Adder"]["file"], str(folder / "Adder.v"))


if __name__ == "__main__":
    unittest.main()
