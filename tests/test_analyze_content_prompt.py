import unittest

from app.core.prompts.analyze_content import ANALYZE_CONTENT_PROMPT


class AnalyzeContentPromptTest(unittest.TestCase):
    def test_prompt_requests_natural_lines_without_bullets(self):
        self.assertIn("display_points: 4-5 short lines", ANALYZE_CONTENT_PROMPT)
        self.assertIn("natural sentence", ANALYZE_CONTENT_PROMPT)
        self.assertIn("include concrete details", ANALYZE_CONTENT_PROMPT)
        self.assertIn("do NOT include bullet markers", ANALYZE_CONTENT_PROMPT)


if __name__ == "__main__":
    unittest.main()
