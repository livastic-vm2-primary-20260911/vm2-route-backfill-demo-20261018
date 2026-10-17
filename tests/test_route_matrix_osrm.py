"""Offline tests; never query public OSRM except the separate explicit demo command."""
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from route_matrix_osrm import (
    PUBLIC_DEMO, build, load_points, make_url, normalized_matrix
)

FIX=Path(__file__).resolve().parents[1]/"fixtures"


def fake_response(durations):
    v=Mock(status_code=200)
    v.json.return_value={"code":"Ok","durations":durations}
    return v


class MatrixTests(unittest.TestCase):
    def test_original_public_synthetic_fixture_has_12_distinct_locations(self):
        p=load_points(FIX/"coordinates_synthetic_sf.csv")
        self.assertEqual(len(p),12)
        self.assertEqual(len({x["location"] for x in p}),12)

    def test_non_synthetic_customer_record_never_egresses(self):
        p=FIX/"coordinates_synthetic_sf.csv"
        with tempfile.TemporaryDirectory() as t:
            q=Path(t)/"points.csv"
            q.write_text(p.read_text().replace("true","false",1))
            with self.assertRaises(ValueError):load_points(q)

    def test_malformed_coordinate_never_egresses(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"p.csv"
            p.write_text("location,lat,lon,synthetic\nA,37.77,-122.42,true\nB,nan,-122.44,true\n")
            with self.assertRaises(ValueError):load_points(p)

    def test_outside_synthetic_sf_demo_box_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"p.csv"
            p.write_text("location,lat,lon,synthetic\nA,37.77,-122.42,true\nB,37.00,-122.44,true\n")
            with self.assertRaises(ValueError):load_points(p)

    def test_duplicate_location_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"p.csv"
            p.write_text("location,lat,lon,synthetic\nA,37.77,-122.42,true\nA,37.78,-122.43,true\n")
            with self.assertRaises(ValueError):load_points(p)

    def test_public_demo_requires_opt_in(self):
        pts=load_points(FIX/"coordinates_synthetic_sf.csv")
        with self.assertRaises(ValueError):make_url(PUBLIC_DEMO,pts,False)
        self.assertIn("/table/v1/driving/",make_url(PUBLIC_DEMO,pts,True))

    def test_unrelated_remote_endpoint_or_embedded_credentials_disallowed(self):
        pts=load_points(FIX/"coordinates_synthetic_sf.csv")
        for endpoint in ("https://example.com","http://169.254.169.254",
                         "http://localhost:5000/secret","http://user:password@localhost:5000",
                         "file:///etc/passwd","https://router.project-osrm.org/other",
                         "http://127.0.0.2:5000"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ValueError):make_url(endpoint,pts,True)

    def test_private_loopback_can_be_configured_without_public_opt_in(self):
        pts=load_points(FIX/"coordinates_synthetic_sf.csv")
        s=make_url("http://127.0.0.1:5000",pts,False)
        self.assertIn("/table/v1/driving/",s)

    def test_all_pairs_durations_are_ceil_rounded(self):
        pts=[{"location":"A","lat":37.77,"lon":-122.41},{"location":"B","lat":37.78,"lon":-122.42}]
        x=normalized_matrix(pts,{"code":"Ok","durations":[[0.0,61.2],[5.4,0]]},"synthetic")
        self.assertEqual(x["minutes"]["A"]["B"],2)
        self.assertEqual(x["minutes"]["B"]["A"],1)
        self.assertEqual(x["source"],"synthetic")
        self.assertTrue(x["synthetic"])

    def test_unreachable_none_is_not_replaced_by_optimistic_synthetic_value(self):
        pts=[{"location":"A"},{"location":"B"}]
        with self.assertRaises(ValueError):
            normalized_matrix(pts,{"code":"Ok","durations":[[0,None],[10,0]]},"failclosed")

    def test_bad_table_shape_rejected(self):
        pts=[{"location":"A"},{"location":"B"}]
        with self.assertRaises(ValueError):
            normalized_matrix(pts,{"code":"Ok","durations":[[0,1]]},"bad")

    def test_fake_table_request_still_gives_fully_labeled_non_customer_data(self):
        pts=load_points(FIX/"coordinates_synthetic_sf.csv")
        n=len(pts)
        rs=fake_response([[0 if i==j else 60 for j in range(n)] for i in range(n)])
        get=Mock(return_value=rs)
        out=build(FIX/"coordinates_synthetic_sf.csv",PUBLIC_DEMO,True,get=get)
        self.assertTrue(out["synthetic"])
        self.assertEqual(len(out["minutes"]),n)
        self.assertIn("ROUTER DEMO",out["source"])
        self.assertEqual(get.call_count,1)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_no_remote_request_on_real_customer_data(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"private.csv"
            p.write_text("location,lat,lon,synthetic\nA,37.77,-122.42,false\nB,37.78,-122.43,false\n")
            get=Mock()
            with self.assertRaises(ValueError):build(p,PUBLIC_DEMO,True,get=get)
            self.assertEqual(get.call_count,0)

if __name__=="__main__":unittest.main()
