#!/usr/bin/env python3
"""Convert SYNTHETIC route locations to a real street-network OSRM time matrix.

Public server is allowed ONLY with --public-synthetic-demo and source rows
explicitly marked synthetic. Never upload actual customer addresses/coordinates
to a third party without the customer's permission and licensing review.
Production should use an explicitly commissioned buyer-approved private router.
No credentials, browser, wallet, trading, payments, messages or uploads.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlparse

import requests

PUBLIC_DEMO = "https://router.project-osrm.org"
PRIVATE_ALLOWED = {"localhost", "127.0.0.1", "::1"}
SAN_FRANCISCO_SYNTHETIC_BOX = (37.70, 37.84, -122.52, -122.35)


def load_points(filename: Path) -> list[dict]:
    with filename.open(newline="", encoding="utf-8") as fh:
        src=list(csv.DictReader(fh))
    if not 2<=len(src)<=15:
        raise ValueError("demo requires 2-15 explicitly synthetic points")
    points=[]; seen=set()
    for row in src:
        place=(row.get("location") or "").strip()
        if not place or place in seen or any(c in place for c in "\r\n:/"):
            raise ValueError("duplicate or invalid opaque location ID")
        seen.add(place)
        try:
            lat=float(row["lat"]);lon=float(row["lon"])
        except (ValueError, KeyError, TypeError):
            raise ValueError("invalid WGS84 coordinate") from None
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:
            raise ValueError("out of bounds coordinate")
        if str(row.get("synthetic") or "").strip().lower()!="true":
            raise ValueError("not explicitly synthetic; refuse remote upload")
        box=SAN_FRANCISCO_SYNTHETIC_BOX
        if not box[0]<=lat<=box[1] or not box[2]<=lon<=box[3]:
            raise ValueError("outside known public San Francisco SYNTHETIC fixture range")
        points.append({"location":place,"lat":lat,"lon":lon})
    return points


def make_url(base: str, rows: list[dict], public_demo: bool) -> str:
    p=urlparse(base)
    if p.path not in ("","/") or p.query or p.fragment or p.username or p.password:
        raise ValueError("unexpected router endpoint path/credentials")
    canonical=base.rstrip("/")
    if canonical==PUBLIC_DEMO:
        if not public_demo:
            raise ValueError("public router needs explicit synthetic-demo opt-in")
    elif p.hostname in PRIVATE_ALLOWED and p.scheme in ("http","https"):
        pass
    else:
        raise ValueError("only loopback self-hosted router or explicit public synthetic demo")
    coords=";".join(f'{v["lon"]:.6f},{v["lat"]:.6f}' for v in rows)
    return canonical+"/table/v1/driving/"+coords+"?annotations=duration"


def normalized_matrix(rows: list[dict], obj: dict, source_label: str) -> dict:
    if not isinstance(obj,dict) or obj.get("code")!="Ok" or not isinstance(obj.get("durations"),list):
        raise ValueError("OSRM missing valid table response")
    dur=obj["durations"];n=len(rows)
    if len(dur)!=n or any(not isinstance(r,list) or len(r)!=n for r in dur):
        raise ValueError("OSRM did not provide complete square matrix")
    names=[r["location"] for r in rows]
    output={}
    for i,origin in enumerate(names):
        output[origin]={}
        for j,dest in enumerate(names):
            value=dur[i][j]
            if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<0:
                raise ValueError("missing/unreachable/invalid routing segment")
            v=int(math.ceil(value/60.0))
            if i==j and v!=0:
                raise ValueError("nonzero diagonal")
            if i!=j and value>0 and v==0:
                raise AssertionError("time rounded below 1 minute")
            if i!=j:output[origin][dest]=v
    return {"source":source_label,"synthetic":True,
            "routingAlgorithm":"OSRM road graph duration table rounded up to whole minutes (no live traffic)",
            "sampledAtUtc":datetime.now(timezone.utc).isoformat(),
            "locations":names,"minutes":output,
            "privacy":"Synthetic public SF demo only. Never send real customers to demo service."}


def build(coords: Path, base: str, public_demo: bool, get=requests.get) -> dict:
    pts=load_points(coords)
    url=make_url(base,pts,public_demo)
    result=get(url,timeout=17,headers={"Accept":"application/json",
           "User-Agent":"VM2-Synthetic-Route-Demo-ReadOnly/1.0"},allow_redirects=False)
    result.raise_for_status()
    if result.status_code!=200:
        raise ValueError("OSRM non-200 response")
    label=("OSRM public ROUTER DEMO; fabricated SF locations; "+str(datetime.now(timezone.utc).date())
           if base.rstrip("/")==PUBLIC_DEMO else "BUYER-APPROVED SELFHOSTED OSRM DRIVING")
    return normalized_matrix(pts,result.json(),label)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--coordinates",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--router",default="http://127.0.0.1:5000")
    parser.add_argument("--public-synthetic-demo",action="store_true")
    a=parser.parse_args()
    result=build(a.coordinates,a.router,a.public_synthetic_demo)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    # Prevent accidental overwrite of other route grids and customer data.
    with a.output.open("x",encoding="utf-8") as fh:
        json.dump(result,fh,indent=2,ensure_ascii=False)
        fh.write("\n")
    print(json.dumps({"source":result["source"],"locations":len(result["locations"]),
                      "synthetic":result["synthetic"],"file":str(a.output)},ensure_ascii=False))


if __name__=="__main__":
    main()
