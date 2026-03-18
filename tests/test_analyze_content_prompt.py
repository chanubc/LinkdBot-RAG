import unittest

from app.core.prompts.analyze_content import ANALYZE_CONTENT_PROMPT


class AnalyzeContentPromptTest(unittest.TestCase):
    def test_prompt_uses_single_readable_semantic_summary(self):
        self.assertIn("semantic_summary: one readable paragraph", ANALYZE_CONTENT_PROMPT)
        self.assertIn("usable for semantic search and as Notion body text", ANALYZE_CONTENT_PROMPT)
        self.assertNotIn("display_points", ANALYZE_CONTENT_PROMPT)


if __name__ == "__main__":
    unittest.main()
