"""No-credential static security checks for the DigitalOcean SSH workflow."""
from pathlib import Path
import unittest

SOURCE = Path(".github/workflows/do-worker-connection-check.yml")


class DigitalOceanSshPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding="utf-8")

    def test_manual_execution_only(self):
        self.assertIn("on:\n  workflow_dispatch:", self.text)
        for forbidden in ("\n  push:", "\n  pull_request:", "\n  schedule:", "\n  repository_dispatch:"):
            self.assertNotIn(forbidden, self.text)
        self.assertIn("github.ref == 'refs/heads/main'", self.text)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.text)

    def test_read_only_ssh_and_least_permissions(self):
        self.assertIn("  contents: read", self.text)
        self.assertIn("environment: digitalocean-news-worker", self.text)
        self.assertIn("gaemi-deploy@$DO_HOST", self.text)
        self.assertIn("systemctl is-active gaemigtp-news.service", self.text)
        self.assertIn("StrictHostKeyChecking=yes", self.text)
        self.assertIn("PasswordAuthentication=no", self.text)
        self.assertIn("BatchMode=yes", self.text)
        for forbidden in ("sudo ", "systemctl restart", "systemctl stop", "scp ", "rsync ", "ssh-keyscan"):
            self.assertNotIn(forbidden, self.text)

    def test_no_embedded_secret_material(self):
        for secret in ("secrets.DO_HOST", "secrets.NEWS_DEPLOY_SSH_KEY", "secrets.NEWS_SSH_KNOWN_HOSTS"):
            self.assertIn(secret, self.text)
        self.assertIn('chmod 600 "$HOME/.ssh/id_ed25519"', self.text)
        self.assertIn("if: always()", self.text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", self.text)


if __name__ == "__main__":
    unittest.main()
