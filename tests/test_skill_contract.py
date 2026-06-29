import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_weekly_email_instructions_use_html_handoff_contract(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        prompt = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

        for text in (skill, prompt):
            self.assertIn("email_handoff.html_body", text)
            self.assertIn("text/html", text)
            self.assertNotIn("email_handoff.markdown_body", text)


if __name__ == "__main__":
    unittest.main()
