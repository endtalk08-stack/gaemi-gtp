import json
import runpy
import unittest

MODULE = runpy.run_path("ops/do-gateway/ai_test_env_presence.py")
build_diagnostic = MODULE["build_diagnostic"]


class AiTestEnvPresenceTests(unittest.TestCase):
    def test_reports_presence_without_exposing_values(self):
        env = {
            "AI_TEST_TOKEN": "do-not-print-this-token",
            "AI_TEST_ENABLED": "1",
            "GROQ_API_KEY": "do-not-print-this-key",
        }
        result = build_diagnostic(env)
        encoded = json.dumps(result)
        self.assertEqual(result["AI_TEST_TOKEN"], {"configured": True})
        self.assertEqual(result["AI_TEST_ENABLED"], {"state": "enabled"})
        self.assertEqual(result["GROQ_API_KEY"], {"configured": True})
        self.assertNotIn("do-not-print-this-token", encoded)
        self.assertNotIn("do-not-print-this-key", encoded)

    def test_missing_and_disabled_values(self):
        result = build_diagnostic({
            "AI_TEST_TOKEN": "   ",
            "AI_TEST_ENABLED": "0",
            "GROQ_API_KEY": "",
        })
        self.assertEqual(result["AI_TEST_TOKEN"], {"configured": False})
        self.assertEqual(result["AI_TEST_ENABLED"], {"state": "disabled"})
        self.assertEqual(result["GROQ_API_KEY"], {"configured": False})

    def test_missing_enabled_flag(self):
        result = build_diagnostic({})
        self.assertEqual(result["AI_TEST_ENABLED"], {"state": "missing"})


if __name__ == "__main__":
    unittest.main()
