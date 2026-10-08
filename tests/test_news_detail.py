import unittest

from backend.services.news_detail import extract_article_text


class NewsDetailTests(unittest.TestCase):
    def test_extracts_article_paragraphs_instead_of_navigation(self):
        payload = b"""
        <html><head><meta name="description" content="Short fallback description"></head>
        <body>
          <nav><p>This navigation paragraph should not become the article body because it is only page chrome.</p></nav>
          <article>
            <p>Google introduced the Gemini agent for enterprise work across Gmail, Drive, Docs and other services.</p>
            <p>The new agent can connect to business systems and complete multi-step tasks for users.</p>
          </article>
        </body></html>
        """

        text = extract_article_text(payload)

        self.assertIn("Gemini agent", text)
        self.assertIn("multi-step tasks", text)
        self.assertNotIn("navigation paragraph", text)

    def test_extracts_json_ld_article_body_when_available(self):
        payload = b"""
        <html><body>
        <script type="application/ld+json">
        {"@type":"NewsArticle","articleBody":"Alphabet announced a new Gemini enterprise product for business customers with additional workflow capabilities."}
        </script>
        <main><p>Short page paragraph that is less complete than the structured article body.</p></main>
        </body></html>
        """

        text = extract_article_text(payload)

        self.assertTrue(text.startswith("Alphabet announced"))
        self.assertIn("Gemini enterprise product", text)


if __name__ == "__main__":
    unittest.main()
