import csv
from datetime import date
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from route_planner import Matrix, backfill, choose_jobs, clock, gaps, minutes, plan, prep_crews, prep_jobs, records, simulate

FIX=ROOT/"fixtures"

def sample():
    cs=prep_crews(records(FIX/"crews.csv"))
    js=prep_jobs(records(FIX/"jobs.csv"))
    people=records(FIX/"customers.csv")
    mx=Matrix(json.loads((FIX/"travel_matrix.json").read_text()))
    return cs,js,people,mx

class RoutePlannerSyntheticTests(unittest.TestCase):
    def test_job_conservation_and_unassignable_reason(self):
        cs,js,ps,mx=sample()
        p=plan(cs,js,ps,mx,date(2026,10,18))
        self.assertEqual(len(js), len(p["unassigned"])+sum(len(s["schedule"]) for s in p["routes"].values()))
        self.assertEqual(p["unassigned"][0]["job_id"],"job-UNASSIGNABLE")
        self.assertIn("reason",p["unassigned"][0])

    def test_every_scheduled_job_has_skill(self):
        cs,js,ps,mx=sample()
        routes, unassigned=choose_jobs(cs,js,mx)
        by_id={c["id"]:c for c in cs}
        for cid,route in routes.items():
            for task in route:self.assertIn(task["skill"],by_id[cid]["skills"])

    def test_every_job_within_window_and_shift(self):
        cs,js,ps,mx=sample()
        routes,_=choose_jobs(cs,js,mx)
        for c in cs:
            record=simulate(c,routes[c["id"]],mx)
            self.assertIsNotNone(record)
            lookup={j["id"]:j for j in js}
            for item in record["jobs"]:
                job=lookup[item["job_id"]]
                self.assertGreaterEqual(minutes(item["start"]),job["start"])
                self.assertLessEqual(minutes(item["end"]),job["end"])
                self.assertLessEqual(minutes(item["end"]),c["end"])
            self.assertLessEqual(minutes(record["back_at"]),c["end"])

    def test_dnc_optout_and_unknown_not_suggested(self):
        cs,js,ps,mx=sample()
        out=plan(cs,js,ps,mx,date(2026,10,18))
        names={s["customer_id"] for s in out["backfill_suggestions_drafts_only"]}
        self.assertNotIn("cust-optout",names)
        self.assertNotIn("cust-undated",names)
        self.assertNotIn("cust-noaddr",names)

    def test_duplicate_address_deduplicated(self):
        cs,js,ps,mx=sample()
        out=plan(cs,js,ps,mx,date(2026,10,18))
        names={s["customer_id"] for s in out["backfill_suggestions_drafts_only"]}
        self.assertIn("cust-due",names)
        self.assertNotIn("cust-duplicate",names)

    def test_backfill_has_explicit_reason_and_draft_not_sent(self):
        cs,js,ps,mx=sample()
        out=plan(cs,js,ps,mx,date(2026,10,18))
        self.assertFalse(out["did_send_outreach"])
        self.assertTrue(all("reason" in x and "draft_not_sent" in x for x in out["backfill_suggestions_drafts_only"]))
        self.assertTrue(all(x["draft_not_sent"].endswith("Would you like our team to contact you about scheduling?") for x in out["backfill_suggestions_drafts_only"]))

    def test_skills_cannot_overrule_time_window(self):
        cs,js,ps,mx=sample()
        unrealistic={"id":"blocked","location":"J1","duration":90,"start":minutes("08:00"),"end":minutes("08:01"),"skill":"plumbing"}
        self.assertIsNone(simulate(cs[0],[unrealistic],mx))

    def test_missing_road_edge_fails_closed(self):
        cs,js,ps,mx=sample()
        blank=Matrix({"source":"broken incomplete matrix","synthetic":True,"minutes":{"D0":{},"D10":{}}})
        routes, unassigned=choose_jobs(cs,js,blank)
        self.assertTrue(all(len(q)==0 for q in routes.values()))
        self.assertEqual(len(js),len(unassigned))

    def test_early_customer_service_not_due(self):
        cs,js,ps,mx=sample()
        out=plan(cs,js,ps,mx,date(2026,7,15))
        ids={x["customer_id"] for x in out["backfill_suggestions_drafts_only"]}
        self.assertNotIn("cust-due",ids)

    def test_open_quote_without_history_is_flagged_lower(self):
        cs,js,ps,mx=sample()
        out=plan(cs,js,ps,mx,date(2026,10,18))
        rows=[x for x in out["backfill_suggestions_drafts_only"] if x["customer_id"]=="cust-quote"]
        self.assertGreater(len(rows),0)
        self.assertTrue(all(x["confidence"]=="lower" for x in rows))

    def test_no_unsolicited_network_access(self):
        # Only local fixtures and supplied travel matrix; no third-party API is called.
        import inspect,route_planner
        txt=inspect.getsource(route_planner)
        self.assertNotIn("requests.get",txt)
        self.assertNotIn("urllib.request",txt)
        self.assertNotIn("smtplib",txt)

    def test_clock_parse_rejects_invalid(self):
        with self.assertRaises(ValueError):minutes("25:00")

if __name__=="__main__":unittest.main()
