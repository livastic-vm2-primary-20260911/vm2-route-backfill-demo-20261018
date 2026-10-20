"""No-network checks for static, buyer-facing synthetic simulation preview."""
import json
import unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
class StaticSiteTests(unittest.TestCase):
    def test_public_demo_only_reproducible_synthetic_output(self):
        p=json.loads((BASE/"docs/synthetic_plan.json").read_text())
        self.assertIs(p["synthetic_only_demo"],True)
        self.assertIs(p["did_send_outreach"],False)
        self.assertEqual(list(p["routes"]),["north","south"])
        self.assertEqual(sum(len(c["schedule"]) for c in p["routes"].values()),5)
        self.assertEqual(len(p["unassigned"]),1)
        self.assertEqual(len(p["backfill_suggestions_drafts_only"]),6)
    def test_page_transparent_and_no_credential_inputs(self):
        s=(BASE/"docs/index.html").read_text()
        self.assertIn("not real-time traffic",s)
        self.assertIn("no funded buyer award",s.lower())
        self.assertIn("privacy-preserving",s.lower())
        self.assertIn('id="schedule-rows"',s)
        self.assertIn('id="gap-rows"',s)
        self.assertIn('id="backfill-rows"',s)
        self.assertNotIn('type="password"',s)
        self.assertNotIn('<iframe',s)
        self.assertNotIn('<form ',s)
        self.assertNotIn("gtag(",s)
        self.assertNotIn("google-analytics",s)
    def test_fixtures_contain_no_personal_contact_or_wallet_fields(self):
        s=(BASE/"docs/synthetic_plan.json").read_text().lower()
        for bad in ["private_key","api_key","seed phrase","onecursor","phone","@gmail.com","payto","walletaddress"]:
            self.assertNotIn(bad,s)
    def test_route_choices_and_no_cdn_scripts(self):
        s=(BASE/"docs/index.html").read_text()
        for x in ['value="north"','value="south"','cache:"no-store"','textContent=','replaceChildren()']:
            self.assertIn(x,s)
        self.assertNotIn('src="https://',s)
        self.assertIn('"@type":"SoftwareSourceCode"',s)
if __name__=="__main__":unittest.main()
