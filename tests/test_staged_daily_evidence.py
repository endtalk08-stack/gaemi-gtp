"""Offline evidence persistence tests, no Neon connection."""
import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "ops" / "staged_issue_evidence.py"
spec = importlib.util.spec_from_file_location("staged_issue_evidence", PATH)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.rows = []
        self.writes = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        if sql.lstrip().startswith("SELECT"):
            self.rows = [self.db[k] for k in params[0] if k in self.db]
        elif sql.lstrip().startswith("INSERT"):
            self.writes.append(params)
        else:
            raise AssertionError(sql)

    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, db):
        self.db = db
        self.last = None

    def cursor(self):
        self.last = FakeCursor(self.db)
        return self.last


class IssueEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConn({
            1: (1, "hash1", "https://publisher.example/news/1", "Original headline", "Example News"),
            2: (2, "hash2", "https://publisher.example/news/2", "Other headline", "Another News"),
        })

    def test_snapshots_only_collected_urls(self):
        self.assertEqual(evidence.persist_issue_evidence(self.conn, 99, [1, 2]), 2)
        self.assertEqual(len(self.conn.last.writes), 2)
        self.assertEqual(self.conn.last.writes[0][2], "https://publisher.example/news/1")
        self.assertEqual(self.conn.last.writes[0][4], "Example News")

    def test_missing_article_refuses_partial_snapshot(self):
        with self.assertRaises(ValueError):
            evidence.persist_issue_evidence(self.conn, 99, [1, 404])
        self.assertEqual(self.conn.last.writes, [])

    def test_mismatched_returned_article_id_rejected(self):
        self.conn.db[1] = (999, "hash1", "https://publisher.example/news/1", "Original headline", "Example News")
        with self.assertRaisesRegex(ValueError, "do not match"):
            evidence.persist_issue_evidence(self.conn, 99, [1])
        self.assertEqual(self.conn.last.writes, [])

    def test_duplicate_article_is_saved_once(self):
        self.assertEqual(evidence.persist_issue_evidence(self.conn, 99, [1, 1]), 1)

    def test_empty_article_list_writes_nothing(self):
        self.assertEqual(evidence.persist_issue_evidence(self.conn, 99, []), 0)

    def test_bad_url_is_rejected(self):
        self.conn.db[1] = (1, "hash1", "javascript:alert(1)", "Bad URL", "Example News")
        with self.assertRaises(ValueError):
            evidence.persist_issue_evidence(self.conn, 99, [1])
        self.assertEqual(self.conn.last.writes, [])

    def test_null_url_rejected_without_partial_write(self):
        self.conn.db[2] = (2, "hash2", None, "Other headline", "Another News")
        with self.assertRaisesRegex(ValueError, "Invalid collected article URL"):
            evidence.persist_issue_evidence(self.conn, 99, [1, 2])
        self.assertEqual(self.conn.last.writes, [])

    def test_boolean_issue_id_rejected(self):
        with self.assertRaises(ValueError):
            evidence.persist_issue_evidence(self.conn, True, [1])

    def test_boolean_article_id_rejected(self):
        with self.assertRaises(ValueError):
            evidence.persist_issue_evidence(self.conn, 99, [True])

    def test_url_with_credentials_rejected(self):
        self.conn.db[1] = (1, "hash1", "https://user:pass@publisher.example/story", "Title", "Publisher")
        with self.assertRaises(ValueError):
            evidence.persist_issue_evidence(self.conn, 99, [1])
        self.assertEqual(self.conn.last.writes, [])

    def test_invalid_issue_id_rejected(self):
        with self.assertRaises(ValueError):
            evidence.persist_issue_evidence(self.conn, 0, [1])


if __name__ == "__main__":
    unittest.main()
