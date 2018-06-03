from . import context
import unittest
import poppy.core
import poppy.file_parser

import os.path
from tempfile import TemporaryDirectory
import numpy as np
import sympy as sym


class YAMLTest(unittest.TestCase):
    """Test that the YAML converter meets the YAML standard."""

    def setUp(self):
        self.example_input_text = ('Species:\n  - x_s\n  - x_i\n  - x_r\n\nParameters:\n  k_s: '
                                   '0.01\n  k_i: 1\n  k_r: 0.05\n\nReactions:\n  - x_s + x_i => '
                                   'x_i + x_i\n  - x_i => x_r\n  - x_r => x_s\n\nRate functions:\n'
                                   '  - k_i * x_i * x_s / N\n  - k_r * x_i\n  - k_s * x_r\n\n'
                                   'Initial conditions:\n  x_s: 80\n  x_i: 20\n  x_r: 0\n\nSystem '
                                   'size:\n  N: 100\n\nSimulation: SSA\n\nObservables:\n  - tot = '
                                   'x + y\n\nProperties:\n  x_s: 43\n')
        self.expected_converted_dictionary = {'Species': ['x_s', 'x_i', 'x_r'],
                                              'Parameters': {'k_i': 1, 'k_r': 0.05, 'k_s': 0.01},
                                              'Reactions': ['x_s + x_i => x_i + x_i',
                                                            'x_i => x_r',
                                                            'x_r => x_s'],
                                              'Rate functions': ['k_i * x_i * x_s / N',
                                                                 'k_r * x_i', 'k_s * x_r'],
                                              'Initial conditions': {'x_i': 20, 'x_r': 0, 'x_s': 80},
                                              'Properties': {'x_s': 43},
                                              'Observables': ['tot = x + y'],
                                              'Simulation': 'SSA',
                                              'System size': {'N': 100}
                                              }

    def test_interpret_file_from_yaml_to_dict(self):
        self.assertTrue(self.expected_converted_dictionary ==
                        poppy.file_parser.yaml_string_to_dict_converter(self.example_input_text))

    def test_interpret_empty_file_from_yaml_to_dict(self):
        empty_input_file = ""
        self.assertIsNone(poppy.file_parser.yaml_string_to_dict_converter(empty_input_file))

    def test_filename_to_dict(self):
        with TemporaryDirectory() as tmpdirname:
            temp_filename = os.path.join(tmpdirname, "test_input.txt")
            with open(temp_filename, "w") as temp_fd:
                temp_fd.write(self.example_input_text)

            self.assertTrue(self.expected_converted_dictionary ==
                            poppy.file_parser.filename_to_dict_converter(temp_filename))

    def test_empty_filename(self):
        with TemporaryDirectory() as tmpdirname:
            temp_filename = os.path.join(tmpdirname, "test_input.txt")
            with open(temp_filename, "w") as temp_fd:
                temp_fd.write("")
            self.assertIsNone(poppy.file_parser.filename_to_dict_converter(temp_filename))

            with open(temp_filename, "w") as temp_fd:
                temp_fd.write("\n")
            self.assertIsNone(poppy.file_parser.filename_to_dict_converter(temp_filename))

    def test_non_existing_filename(self):
        with TemporaryDirectory() as tmpdirname:
            temp_filename = os.path.join(tmpdirname, "test_input.txt")
            with self.assertRaises(FileNotFoundError):
                poppy.file_parser.filename_to_dict_converter(temp_filename)

    def tearDown(self):
        # Here we can place repetitive code that should be performed _after_ every test is executed.
        pass


class ParserTest(unittest.TestCase):
    """Test that the parser is able to correctly convert reactions and rate functions."""

    def setUp(self):
        self.input_data = {"Species": poppy.core.VariableCollection(["x_s", "x_i", "x_r"]),
                           "Parameters": poppy.core.ParameterCollection({'k_i': 1,
                                                                         'k_r': 0.05,
                                                                         'k_s': 0.01,
                                                                         'N': 100}),
                           "Rate functions": ["4 - 6",
                                              "k_i * x_i * x_s /    N  ",
                                              "-3* 2 * k_i * x_i * x_s / max(x_s, x_i) + 2 * x_i - x_i + x_r"],
                           "Reactions": ["x_s => x_i",
                                         "x_s + x_i => x_r",
                                         "3x_s + x_i => x_r"],
                           "Initial conditions": np.array([80, 20, 0]),
                           }
        self.expected_update_vector = [np.array([-1, 1, 0]),
                                       np.array([-1, -1, 1]),
                                       np.array([-3, -1, 1])]

        x_s, x_i, x_r = sym.symbols("x_s x_i x_r")
        self.expected_rate_functions = [sym.Integer(-2),
                                        x_s * x_i / 100,
                                        -6.0 * x_s * x_i / sym.Max(x_i, x_s) + 1.0 * x_i + x_r]

        self.rate_func_coll = poppy.core.RateFunctionCollection(self.input_data["Rate functions"],
                                                                self.input_data["Species"],
                                                                self.input_data["Parameters"])

    def test_convert_all_reactions(self):
        for i, _ in enumerate(self.input_data["Reactions"]):
            reaction_obj = poppy.core.Reaction(self.input_data["Reactions"][i],
                                               self.input_data["Species"])

            self.assertEqual(np.array_equiv(reaction_obj.update_vector,
                                            self.expected_update_vector[i]), True)

    def test_missing_value_raises_exc(self):
        with self.assertRaisesRegex(ValueError, "Unable to find reagent '.*' inside the list of variables"):
            poppy.core.Reaction("R1 + R2 => 2 P1", self.input_data["Species"])

    def test_reaction_collection(self):
        reaction_collection = poppy.core.ReactionCollection(self.input_data["Reactions"],
                                                            self.input_data["Species"])

        for reac, upd_vec in zip(reaction_collection, self.expected_update_vector):
            self.assertEqual(np.array_equiv(reac.update_vector, upd_vec), True)

    def test_all_rate_functions(self):
        for i, _ in enumerate(self.input_data["Rate functions"]):
            rate_func = poppy.core.RateFunction(self.input_data["Rate functions"][i],
                                                self.input_data["Species"],
                                                self.input_data["Parameters"])
            self.assertEqual(rate_func.sym_function, self.expected_rate_functions[i])

    def test_rate_functions_collection_symbolic_arg(self):
        for i, rate_func in enumerate(self.rate_func_coll):
            self.assertEqual(rate_func.sym_function, self.expected_rate_functions[i])

    def test_rate_functions_collection_compute_in_points(self):
        self.assertEqual(True, np.allclose(self.rate_func_coll(self.input_data["Initial conditions"]),
                                           [-2., 16., -100.]))

    def test_rate_functions_collection_compute_dim_mismatch_exc(self):
        with self.assertRaisesRegex(ValueError, "Array shapes mismatch: input vector \d, rate functions \d."):
            self.rate_func_coll(np.array([1, 2]))
