import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_weekly_email_instructions_use_himalaya_mml_contract(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        prompt = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

        for text in (skill, prompt):
            self.assertIn("email_handoff.mml_template", text)
            self.assertIn("himalaya", text.casefold())
            self.assertIn("never_automatic", text)
            self.assertNotIn("email_handoff.html_body", text)
            self.assertNotIn(
                "text/html through an explicit HTML-capable email field",
                text,
            )

    def test_weekly_reference_prohibits_blind_himalaya_retry(self):
        reference = (ROOT / "references" / "weekly-automation.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("himalaya --account <account> template send", reference)
        self.assertIn("[Gmail]/Sent Mail", reference)
        self.assertIn("must not automatically retry", reference)


if __name__ == "__main__":
    unittest.main()
