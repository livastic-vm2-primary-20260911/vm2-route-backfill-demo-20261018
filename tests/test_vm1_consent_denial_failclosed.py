"""VM1 independent, synthetic-only consent encoding QA for VM2 buyer's pending route planner.

A CRM's do_not_contact/opt_out exports can contain categorical denial text
instead of normalized booleans. The scheduler must not reclassify a warning
or a malformed denial as "false" and propose contacting that customer.
"""
import copy
from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from route_planner import plan
from test_route_planner import sample

DAY=date(2026, 10, 18)


def backfill_ids(people):
    crews,jobs,_,matrix=sample()
    out=plan(crews,jobs,people,matrix,DAY)
    assert out["did_send_outreach"] is False
    return {x["customer_id"] for x in out["backfill_suggestions_drafts_only"]}


class UnknownConsentEncodingFailsClosed(unittest.TestCase):
    def setUp(self):
        _,_,people,_=sample()
        self.original=copy.deepcopy(people[0])
        assert self.original["customer_id"] == "cust-due"

    def test_dnc_text_must_not_be_treated_as_contact_consent(self):
        row=copy.deepcopy(self.original)
        row["do_not_contact"]="DNC"
        self.assertNotIn("cust-due",backfill_ids([row]))

    def test_opted_out_text_must_not_be_treated_as_contact_consent(self):
        row=copy.deepcopy(self.original)
        row["opt_out"]="opted out"
        self.assertNotIn("cust-due",backfill_ids([row]))

    def test_unrecognized_denial_value_must_fail_closed(self):
        row=copy.deepcopy(self.original)
        row["do_not_contact"]="?"
        self.assertNotIn("cust-due",backfill_ids([row]))

    def test_duplicate_denial_must_suppress_earlier_eligible_customer(self):
        prior=copy.deepcopy(self.original)
        later=copy.deepcopy(prior)
        later["opt_out"]="unsubscribed"
        self.assertNotIn("cust-due",backfill_ids([prior,later]))

    def test_denial_at_shared_address_blocks_other_customer(self):
        first=copy.deepcopy(self.original)
        second=copy.deepcopy(first)
        second["customer_id"]="cohabitant"
        second["do_not_contact"]="DO NOT CONTACT"
        self.assertNotIn("cust-due",backfill_ids([first,second]))

    def test_definite_false_legacy_values_remain_eligible(self):
        row=copy.deepcopy(self.original)
        row["do_not_contact"]="False"
        row["opt_out"]=" No "
        self.assertIn("cust-due",backfill_ids([row]))

    def test_empty_legacy_false_values_remain_eligible(self):
        row=copy.deepcopy(self.original)
        row["do_not_contact"]=""
        row["opt_out"]="0"
        self.assertIn("cust-due",backfill_ids([row]))


if __name__ == "__main__":
    unittest.main()
