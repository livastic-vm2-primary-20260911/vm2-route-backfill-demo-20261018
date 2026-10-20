#!/usr/bin/env python3
"""Offline, synthetic-data field-service scheduling feasibility prototype.

No network calls, client uploads, outbound messages or payout/wallet operations.
Drive minutes are explicit inputs from an authorized routing provider; synthetic
fixture drives may be used only for a demo, not represented as real road times.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date
import json
import math
from pathlib import Path
from typing import Any


def minutes(value: str) -> int:
    hh, mm = (int(x) for x in value.split(":"))
    if not (0 <= hh < 24 and 0 <= mm < 60):
        raise ValueError("bad HH:MM")
    return hh * 60 + mm


def clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def truthy(v: Any) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def contact_denied(v: Any) -> bool:
    """Treat unknown NONEMPTY CRM suppression codes as denial, not consent.

    Legacy clean exports use blank/0/false/no/n/off for no suppression;
    a value such as DNC, unsubscribed, opted out, or '?' must fail closed.
    """
    if v is None:
        return False
    return str(v).strip().casefold() not in {"", "0", "false", "no", "n", "off"}


def records(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def prep_crews(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        c = {"id": row["crew_id"], "start": minutes(row["start"]),
             "end": minutes(row["end"]), "depot": row["start_location"],
             "skills": {s.strip().lower() for s in row["skills"].split("|") if s.strip()}}
        if c["start"] >= c["end"] or not c["depot"]:
            raise ValueError("invalid crew shift")
        out.append(c)
    if len({x["id"] for x in out}) != len(out):
        raise ValueError("duplicate crew id")
    return out


def prep_jobs(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        j = {"id": row["job_id"], "location": row["location"],
             "duration": int(row["duration_minutes"]),
             "start": minutes(row["window_start"]), "end": minutes(row["window_end"]),
             "skill": row["required_skill"].strip().lower()}
        if j["duration"] < 1 or j["start"] >= j["end"] or not j["location"]:
            raise ValueError("invalid job")
        out.append(j)
    if len({x["id"] for x in out}) != len(out):
        raise ValueError("duplicate job id")
    return out


class Matrix:
    def __init__(self, data: dict):
        self.source = data["source"]
        self.synthetic = bool(data.get("synthetic", False))
        self.values = data["minutes"]
        if not isinstance(self.values, dict):
            raise ValueError("bad travel matrix")

    def travel(self, start: str, finish: str) -> int:
        if start == finish:
            return 0
        row = self.values.get(start)
        if not isinstance(row, dict):
            raise ValueError("invalid travel matrix row")
        value = row.get(finish)
        if value is None:
            raise KeyError(f"missing travel time {start}->{finish}")
        # Never coerce a buyer-provided travel duration: int(2.9) rounds DOWN
        # and int(True) silently becomes one minute, both unsafe for dispatch.
        # Normalized OSRM matrices already contain ceiled integer minutes.
        if type(value) is not int or value < 0 or value > 24 * 60:
            raise ValueError("invalid travel time: expected integer minutes")
        return value


def simulate(crew: dict, jobs: list[dict], matrix: Matrix) -> dict | None:
    now, loc, total = crew["start"], crew["depot"], 0
    visits: list[dict] = []
    try:
        for j in jobs:
            if j["skill"] not in crew["skills"]:
                return None
            drive = matrix.travel(loc, j["location"])
            arrive = now + drive
            start = max(arrive, j["start"])
            end = start + j["duration"]
            if end > j["end"] or end > crew["end"]:
                return None
            visits.append({"job_id": j["id"], "location": j["location"],
                           "arrive": clock(arrive), "start": clock(start),
                           "end": clock(end), "drive_minutes": drive,
                           "start_min": start, "end_min": end})
            total += drive
            now, loc = end, j["location"]
        last_drive = matrix.travel(loc, crew["depot"])
        if now + last_drive > crew["end"]:
            return None
        total += last_drive
    except (KeyError, ValueError):
        return None
    return {"jobs": visits, "total_drive_minutes": total, "back_at": clock(now + last_drive)}


def choose_jobs(crews: list[dict], jobs: list[dict], matrix: Matrix):
    routes = {c["id"]: [] for c in crews}
    unassigned: list[dict] = []
    # Most constrained work first; never silently lose a job.
    eligible = {j["id"]:sum(j["skill"] in c["skills"] for c in crews) for j in jobs}
    ordered = sorted(jobs, key=lambda j:(eligible[j["id"]], j["end"]-j["start"],
                                          j["end"], j["id"]))
    for j in ordered:
        best = None
        for c in crews:
            existing = routes[c["id"]]
            old = simulate(c, existing, matrix)
            if old is None:
                raise AssertionError("existing route became infeasible")
            for ix in range(len(existing)+1):
                new = existing[:ix]+[j]+existing[ix:]
                res = simulate(c,new,matrix)
                if res is None:continue
                extra = res["total_drive_minutes"]-old["total_drive_minutes"]
                val=(extra,res["total_drive_minutes"],c["id"],ix)
                if best is None or val < best[0]:
                    best=(val,c,new)
        if best is None:
            unassigned.append({"job_id":j["id"],"reason":
                "no skill-matching feasible insertion within shift/window, or routing data unavailable"})
        else:
            _,c,seq=best
            routes[c["id"]]=seq
    return routes,unassigned


def gaps(crew: dict, route: list[dict], matrix: Matrix, minimum: int) -> list[dict]:
    result=simulate(crew,route,matrix)
    assert result is not None
    output=[]
    now,loc=crew["start"],crew["depot"]
    pairs=list(zip(route,result["jobs"]))
    for pos in range(len(route)+1):
        if pos<len(route):
            next_j, next_visit=pairs[pos]
            depart_limit=next_visit["start_min"]-matrix.travel(loc,next_j["location"])
        else:
            depart_limit=crew["end"]-matrix.travel(loc,crew["depot"])
        if depart_limit-now>=minimum:
            output.append({"crew_id":crew["id"],"after_job":(route[pos-1]["id"] if pos else None),
                           "position":pos,"from_min":now,"until_min":depart_limit,
                           "from":clock(now),"until":clock(depart_limit),
                           "near_location":loc})
        if pos<len(route):
            now=next_visit["end_min"]
            loc=next_j["location"]
    return output


def backfill(crews: list[dict], routes: dict, people: list[dict],
             matrix: Matrix, today: date, min_gap: int):
    # Scan ALL source rows before proposing anything. CSV exports commonly include
    # repeated customer IDs or an older row that still claims contact permission
    # despite a later opt-out. Suppress the whole identity (and shared address)
    # on ANY denial, regardless of input row order. Never send outbound messages.
    blocked_ids=set()
    blocked_locations=set()
    conflicting_ids=set()
    identity_facts={}
    for raw in people:
        contact=str(raw.get("customer_id") or "").strip()
        location=str(raw.get("location") or "").strip().casefold().replace(" ","")
        if contact_denied(raw.get("do_not_contact")) or contact_denied(raw.get("opt_out")):
            if contact:blocked_ids.add(contact)
            if location:blocked_locations.add(location)
        if not contact or not location:continue
        # Never trust an older duplicate record when a second export says the
        # same ID has a different service history, interval, address or quote.
        facts=(location,
               str(raw.get("last_service_date") or "").strip(),
               str(raw.get("service_interval_days") or "").strip(),
               str(raw.get("open_quote") or "").strip().lower(),
               str(raw.get("required_skill") or "").strip().lower(),
               str(raw.get("duration_minutes") or "").strip())
        old=identity_facts.setdefault(contact,facts)
        if old!=facts:conflicting_ids.add(contact)

    clean={}
    for raw in people:
        contact=str(raw.get("customer_id") or "").strip()
        location=str(raw.get("location") or "").strip()
        dedupe=location.casefold().replace(" ","")
        if (not contact or not location or contact in blocked_ids
                or dedupe in blocked_locations or contact in conflicting_ids):
            continue
        if dedupe in clean:continue
        last=raw.get("last_service_date") or ""
        plan=raw.get("service_interval_days") or ""
        open_quote=truthy(raw.get("open_quote"))
        try:
            interval=int(plan) if plan else None
            days=(today-date.fromisoformat(last)).days if last else None
            if days is not None and days < 0:continue
            due=days is not None and interval is not None and interval>0 and days>=interval
        except (ValueError,TypeError):
            due=False
        if not (due or open_quote):continue
        if raw.get("required_skill") is None or not str(raw["required_skill"]).strip():continue
        try:
            duration=int(raw.get("duration_minutes") or 0)
        except (ValueError,TypeError):
            # A malformed customer CSV must not abort an otherwise safe route.
            continue
        if duration<1:continue
        reason=("service interval "+str(days)+"/"+str(interval)+" days" if due
                else "buyer-marked outstanding quote")
        clean[dedupe]={"id":contact,"location":location,"duration":duration,
                       "skill":raw["required_skill"].strip().lower(),
                       "reason":reason, "confidence":"higher" if due else "lower",
                       "name":str(raw.get("name") or "Customer")[:80]}
    proposals=[]
    for crew in crews:
        route=routes[crew["id"]]
        for gap in gaps(crew,route,matrix,min_gap):
            for c in clean.values():
                if c["skill"] not in crew["skills"]:continue
                # Confirm the *entire route* stays valid after insertion.
                candidate={"id":"potential-"+c["id"],"location":c["location"],
                           "duration":c["duration"],"start":gap["from_min"],
                           "end":gap["until_min"],"skill":c["skill"]}
                new=route[:gap["position"]]+[candidate]+route[gap["position"]:]
                test=simulate(crew,new,matrix)
                if test is None:continue
                extra=test["total_drive_minutes"]-simulate(crew,route,matrix)["total_drive_minutes"]
                proposals.append({"crew_id":crew["id"],"customer_id":c["id"],"location":c["location"],
                                  "gap":gap["from"]+"-"+gap["until"],
                                  "reason":c["reason"],"confidence":c["confidence"],
                                  "extra_drive_minutes":extra,
                                  "draft_not_sent":f"Hello {c['name']}, we have a possible opening near you on {today.isoformat()}."
                                                    " Would you like our team to contact you about scheduling?"})
    return sorted(proposals,key=lambda x:(x["extra_drive_minutes"],x["confidence"]!="higher",x["customer_id"]))


def plan(crews:list[dict], jobs:list[dict], customers:list[dict],
         matrix:Matrix,today:date,min_gap:int=30)->dict:
    routes,unassigned=choose_jobs(crews,jobs,matrix)
    sched={}
    for crew in crews:
        summary=simulate(crew,routes[crew["id"]],matrix)
        assert summary is not None
        sched[crew["id"]]={"schedule":summary["jobs"],
                          "return_to_start":summary["back_at"],
                          "total_drive_minutes":summary["total_drive_minutes"],
                          "gaps":gaps(crew,routes[crew["id"]],matrix,min_gap)}
    assertions= len(jobs)==len(unassigned)+sum(len(x) for x in routes.values())
    if not assertions:raise AssertionError("job conservation violated")
    return {"runDate":str(today),"routing_source":matrix.source,
            "synthetic_only_demo":matrix.synthetic,"did_send_outreach":False,
            "routes":sched,"unassigned":unassigned,
            "backfill_suggestions_drafts_only":backfill(crews,routes,customers,matrix,today,min_gap),
            "notes":["All minutes come from supplied routing matrix; synthetic data must not be represented as actual road times.",
                     "Suggestions are provisional; dispatcher verifies travel/traffic/customer consent before sending.",
                     "Any opt-out in a duplicate customer record blocks that identity and address from outreach suggestions.",
                     "Contradictory duplicate service dates, plans, skills or locations are excluded pending buyer review.",
                     "No customer contact is sent or attempted by this program."]}


def main():
    a=argparse.ArgumentParser()
    for field in ("crews","jobs","customers","matrix"):
        a.add_argument("--"+field,required=True,type=Path)
    a.add_argument("--date",default=str(date.today()))
    a.add_argument("--gap",type=int,default=30)
    ns=a.parse_args()
    if ns.gap<1:raise ValueError("gap must be positive")
    obj=plan(prep_crews(records(ns.crews)),prep_jobs(records(ns.jobs)),
             records(ns.customers),Matrix(json.loads(ns.matrix.read_text())),
             date.fromisoformat(ns.date),ns.gap)
    print(json.dumps(obj,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
