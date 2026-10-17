"""No paid API calls, no database writes."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'ops' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

issues = load('staged_daily_groq_issues')
links = load('staged_issue_links')

class IssueIntegrationTests(unittest.TestCase):
    def test_two_issues_with_verified_sources(self):
        data = '{"issues":[{"headline":"A","summary":"B","tags":["#a"]},{"headline":"C","summary":"D","tags":[]}]}'
        parsed = issues.parse_issues(data)
        self.assertEqual(links.validate_links(len(parsed), {0:[101,102],1:[102]}, [101,102]), [[101,102],[102]])

    def test_unsupported_source_rejected(self):
        parsed = issues.parse_issues('{"issues":[{"headline":"A","summary":"B","tags":[]}]}')
        with self.assertRaises(ValueError):
            links.validate_links(len(parsed), {0:[999]}, [101])

    def test_no_issue_requires_no_sources(self):
        parsed = issues.parse_issues('{"issues":[]}')
        self.assertEqual(links.validate_links(len(parsed), {}, []), [])

if __name__ == '__main__':
    unittest.main()
