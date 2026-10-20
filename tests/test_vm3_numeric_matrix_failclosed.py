"""VM3 independently reproducible, synthetic-only QA for VM2 pending 390-USDC route planner.
No external network, live customer data or payout interactions.
"""
import sys
from pathlib import Path
import unittest
from datetime import date
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from route_planner import Matrix, prep_crews, prep_jobs, plan

class VM3BadRouteMatrixTests(unittest.TestCase):
    def test_fractional_driving_minutes_rejected_not_rounded_down(self):
        m=Matrix({"source":"untrusted buyer JSON","minutes":{"A":{"B":2.9},"B":{"A":2}}})
        with self.assertRaises(ValueError):
            m.travel("A","B")

    def test_boolean_travel_must_not_be_treated_as_one_minute(self):
        m=Matrix({"source":"untrusted JSON","minutes":{"A":{"B":True},"B":{"A":2}}})
        with self.assertRaises(ValueError):
            m.travel("A","B")

    def test_string_number_must_not_pass_as_routing_time(self):
        m=Matrix({"source":"untrusted JSON","minutes":{"A":{"B":"2"},"B":{"A":2}}})
        with self.assertRaises(ValueError):
            m.travel("A","B")

    def test_non_dict_route_row_is_unavailable_not_crash(self):
        m=Matrix({"source":"corrupted table","minutes":{"A":[1,2],"B":{"A":2}}})
        with self.assertRaises(ValueError):
            m.travel("A","B")

    def test_fractional_matrix_never_yields_scheduled_job(self):
        crews=prep_crews([{"crew_id":"C1","start":"08:00","end":"08:15","start_location":"A","skills":"qa"}])
        jobs=prep_jobs([{"job_id":"job1","location":"B","duration_minutes":"9",
                         "window_start":"08:00","window_end":"08:12","required_skill":"qa"}])
        # A->B duration 2.9 must not truncate to 2; the source is malformed and
        # may not safely establish feasibility even if a 3-minute route fits.
        m=Matrix({"source":"untrusted","minutes":{"A":{"B":2.9},"B":{"A":1}}})
        result=plan(crews,jobs,[],m,date(2026,10,20))
        self.assertEqual(len(result["routes"]["C1"]["schedule"]),0)
        self.assertEqual(len(result["unassigned"]),1)
        self.assertFalse(result["did_send_outreach"])

    def test_valid_exact_integer_road_minutes_still_work(self):
        m=Matrix({"source":"offline synthetic","minutes":{"A":{"B":2},"B":{"A":3}}})
        self.assertEqual(m.travel("A","B"),2)
        self.assertEqual(m.travel("B","A"),3)
        self.assertEqual(m.travel("A","A"),0)

if __name__=="__main__":
    unittest.main()
