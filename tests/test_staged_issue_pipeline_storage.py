"""Offline integration: reviewed links through evidence SQL parameters."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops"))
from staged_issue_pipeline import save_verified_evidence


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        if sql.lstrip().startswith("SELECT"):
            self.rows = [self.conn.articles[k] for k in params[0] if k in self.conn.articles]
        elif sql.lstrip().startswith("INSERT"):
            self.conn.saved.append(params)
        else:
            raise AssertionError(sql)

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self):
        self.articles = {
            11: (11, "h11", "https://example.org/11", "Original 11", "Publisher A"),
            12: (12, "h12", "https://example.org/12", "Original 12", "Publisher B"),
        }
        self.saved = []

    def cursor(self):
        return Cursor(self)


class StorageFlowTests(unittest.TestCase):
    def setUp(self):
        self.conn = Connection()

    def test_original_metadata_saved_for_each_issue(self):
        result = save_verified_evidence(
            self.conn, ["issue one", "issue two"],
            {0: [11, 12], 1: [12]}, [11, 12], [101, 102])
        self.assertEqual(result, [2, 1])
        self.assertEqual(len(self.conn.saved), 3)
        self.assertEqual(self.conn.saved[0], (101, "h11", "https://example.org/11", "Original 11", "Publisher A"))
        self.assertEqual(self.conn.saved[2], (102, "h12", "https://example.org/12", "Original 12", "Publisher B"))

    def test_unknown_article_cannot_write(self):
        with self.assertRaises(ValueError):
            save_verified_evidence(self.conn, ["issue"], {0: [999]}, [11], [101])
        self.assertEqual(self.conn.saved, [])

    def test_missing_article_row_cannot_write(self):
        del self.conn.articles[12]
        with self.assertRaises(ValueError):
            save_verified_evidence(self.conn, ["issue"], {0: [11, 12]}, [11, 12], [101])
        self.assertEqual(self.conn.saved, [])


if __name__ == "__main__":
    unittest.main()
