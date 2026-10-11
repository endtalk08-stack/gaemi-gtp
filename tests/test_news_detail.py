import unittest

from backend.services.news_detail import extract_article_text, extract_structured_article_facts


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


    def test_diagnostics_identify_metadata_without_changing_text(self):
        payload = b"""
        <html><head><meta name="description"
        content="A long overview of the company earnings and product launches, without a real article body on this page."></head>
        <body></body></html>
        """
        plain = extract_article_text(payload)
        audit = {}
        with_audit = extract_article_text(payload, diagnostics=audit)
        self.assertEqual(plain, with_audit)
        self.assertEqual(audit["source"], "meta_description")

    def test_diagnostics_identify_article_paragraphs(self):
        payload = b"""
        <html><body><article>
        <p>The company reported a detailed quarterly earnings update with new product investments and improved operational results.</p>
        </article></body></html>
        """
        audit = {}
        result = extract_article_text(payload, diagnostics=audit)
        self.assertIn("quarterly earnings", result)
        self.assertEqual(audit["source"], "article_or_main_paragraphs")

    def test_extracts_structured_contract_facts_from_selected_article(self):
        text = (
            "Google entered a 20-year power agreement with Constellation Energy "
            "in the United States. The $3.6 billion deal covers 3.59 GW, "
            "including 890 MW of nuclear capacity."
        )
        facts = extract_structured_article_facts(
            text,
            {
                "event_owner": "알파벳",
                "relation_type": "direct",
            },
            "알파벳",
            grounded_tags=["Gemini"],
        )

        self.assertEqual(facts["product_name"], "Gemini")
        self.assertEqual(facts["counterparty"], "Constellation Energy")
        self.assertEqual(facts["amount"], "$3.6 billion")
        self.assertIn("미국", facts["region"])
        self.assertEqual(facts["announcer"], "알파벳")
        self.assertIn("20-year", facts["key_numbers"])
        self.assertIn("3.59 GW", facts["key_numbers"])
        self.assertIn("890 MW", facts["key_numbers"])


if __name__ == "__main__":
    unittest.main()
