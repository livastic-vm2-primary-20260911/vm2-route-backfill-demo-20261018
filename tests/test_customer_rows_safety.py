"""Original VM5 independent negative-path tests for VM2 pending 390USDC buyer.
All records are synthetic; no network calls or consumer contact.
"""
import copy
from datetime import date
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from route_planner import plan
from test_route_planner import sample

DAY=date(2026,10,18)

def ids(people):
    crews,jobs,_,matrix=sample()
    report=plan(crews,jobs,people,matrix,DAY)
    assert report['did_send_outreach'] is False
    return {p["customer_id"] for p in report["backfill_suggestions_drafts_only"]}

class BackfillAdversarialCustomerRows(unittest.TestCase):
    def setUp(self):
        _,_,self.people,_=sample()
        self.due=copy.deepcopy(self.people[0])
        self.assertEqual(self.due["customer_id"],"cust-due")

    def test_later_same_customer_optout_must_suppress_prior_eligible_row(self):
        newer=copy.deepcopy(self.due)
        newer["opt_out"]="1"
        self.assertNotIn("cust-due",ids(self.people+[newer]))

    def test_any_do_not_contact_on_same_address_suppresses_outreach_to_shared_location(self):
        newer=copy.deepcopy(self.due)
        newer["customer_id"]="different-occupant"
        newer["do_not_contact"]="true"
        self.assertNotIn("cust-due",ids(self.people+[newer]))

    def test_one_recent_service_date_overrules_stale_due_record(self):
        newer=copy.deepcopy(self.due)
        newer["last_service_date"]="2026-10-17"
        self.assertNotIn("cust-due",ids(self.people+[newer]))

    def test_conflicting_service_plan_interval_fails_closed(self):
        newer=copy.deepcopy(self.due)
        newer["service_interval_days"]="365"
        self.assertNotIn("cust-due",ids(self.people+[newer]))

    def test_one_customer_with_two_distinct_addresses_is_ambiguous(self):
        newer=copy.deepcopy(self.due)
        newer["location"]="C9"
        self.assertNotIn("cust-due",ids(self.people+[newer]))

    def test_non_numeric_customer_duration_skipped_instead_of_crashing_day(self):
        invalid=copy.deepcopy(self.due)
        invalid["customer_id"]="customer-bad-input"
        invalid["location"]="C9"
        invalid["duration_minutes"]="twenty minutes"
        self.assertNotIn("customer-bad-input",ids([invalid]+self.people))
        self.assertIn("cust-due",ids([invalid]+self.people))

    def test_regular_clean_customer_still_appears(self):
        self.assertIn("cust-due",ids(self.people))

if __name__=="__main__":
    unittest.main()
