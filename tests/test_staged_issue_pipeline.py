import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'ops'))
import staged_issue_pipeline as pipeline

class PipelineTests(unittest.TestCase):
    def test_saved_sources(self):
        with patch.object(pipeline, 'persist_issue_evidence', return_value=2) as save:
            result = pipeline.save_verified_evidence(None, ['issue'], {0: [1, 2]}, [1, 2], [51])
            self.assertEqual(result, [2])
            save.assert_called_once_with(None, 51, [1, 2])

    def test_reject_unknown_article(self):
        with patch.object(pipeline, 'persist_issue_evidence') as save:
            with self.assertRaises(ValueError):
                pipeline.save_verified_evidence(None, ['issue'], {0: [99]}, [1], [51])
            save.assert_not_called()

    def test_invalid_issue_id_rejected(self):
        with patch.object(pipeline, 'persist_issue_evidence') as save:
            with self.assertRaises(ValueError):
                pipeline.save_verified_evidence(None, ['issue'], {0: [1]}, [1], [True])
            save.assert_not_called()

    def test_duplicate_issue_ids_rejected(self):
        with patch.object(pipeline, 'persist_issue_evidence') as save:
            with self.assertRaises(ValueError):
                pipeline.save_verified_evidence(None, ['one', 'two'], {0: [1], 1: [2]}, [1, 2], [51, 51])
            save.assert_not_called()

    def test_empty_issues(self):
        with patch.object(pipeline, 'persist_issue_evidence') as save:
            self.assertEqual(pipeline.save_verified_evidence(None, [], {}, [], []), [])
            save.assert_not_called()

if __name__ == '__main__':
    unittest.main()
