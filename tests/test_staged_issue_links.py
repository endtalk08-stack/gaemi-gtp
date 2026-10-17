import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).resolve().parents[1] / 'ops' / 'staged_issue_links.py'
spec = importlib.util.spec_from_file_location('staged_issue_links', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class IssueLinkTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(module.validate_links(2, {0:[11,11,12],1:[12]}, [11,12]), [[11,12],[12]])
    def test_unknown_article(self):
        with self.assertRaises(ValueError):
            module.validate_links(1, {0:[13]}, [11,12])
    def test_missing_mapping(self):
        with self.assertRaises(ValueError):
            module.validate_links(1, {}, [11])
    def test_empty_evidence(self):
        with self.assertRaises(ValueError):
            module.validate_links(1, {0:[]}, [11])
    def test_zero_issues(self):
        self.assertEqual(module.validate_links(0, {}, []), [])
    def test_boolean_mapping_key_rejected(self):
        with self.assertRaises(ValueError):
            module.validate_links(1, {False: [11]}, [11])

    def test_true_mapping_key_rejected(self):
        with self.assertRaises(ValueError):
            module.validate_links(2, {0: [11], True: [12]}, [11, 12])

    def test_boolean_id(self):
        with self.assertRaises(ValueError):
            module.validate_links(1, {0:[True]}, [1])

if __name__ == '__main__':
    unittest.main()
