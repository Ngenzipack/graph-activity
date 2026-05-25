#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import random
import subprocess
from collections import Counter
from pathlib import Path


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def monday_of_week(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def daterange(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def weighted_day_sample(rng: random.Random, week_days):
    weights = []
    for d in week_days:
        if d.weekday() <= 3:  # Mon-Thu
            weights.append(1.3)
        elif d.weekday() == 4:  # Fri
            weights.append(1.1)
        else:  # Sat/Sun
            weights.append(0.35)

    # sample without replacement by repeated weighted picks
    picked = []
    pool = list(week_days)
    pool_weights = list(weights)
    while pool:
        total = sum(pool_weights)
        x = rng.random() * total
        acc = 0.0
        idx = 0
        for i, w in enumerate(pool_weights):
            acc += w
            if acc >= x:
                idx = i
                break
        picked.append(pool.pop(idx))
        pool_weights.pop(idx)
    return picked


def plan_commits(start_date, end_date, min_active_days, max_active_days, max_commits_per_day, skip_weeks_rate, seed):
    rng = random.Random(seed)
    counts = Counter()

    first_week = monday_of_week(start_date)
    last_week = monday_of_week(end_date)

    week = first_week
    while week <= last_week:
        week_days = [d for d in (week + dt.timedelta(days=i) for i in range(7)) if start_date <= d <= end_date]
        if not week_days:
            week += dt.timedelta(days=7)
            continue

        if rng.random() < skip_weeks_rate:
            week += dt.timedelta(days=7)
            continue

        active_days = rng.randint(min_active_days, max_active_days)
        active_days = max(1, min(active_days, len(week_days)))

        ordered_days = weighted_day_sample(rng, week_days)
        chosen_days = sorted(ordered_days[:active_days])

        for day in chosen_days:
            commits_today = rng.randint(1, max_commits_per_day)
            counts[day] += commits_today

        week += dt.timedelta(days=7)

    return counts


def write_activity(path: Path, stamp: str, sequence: int):
    data = json.loads(path.read_text())
    data.setdefault("entries", []).append(
        {
            "sequence": sequence,
            "timestamp": stamp,
            "note": "scheduled activity entry"
        }
    )
    path.write_text(json.dumps(data, indent=2) + "\n")


def run_git(cmd, cwd, env=None):
    subprocess.run(cmd, cwd=cwd, check=True, env=env)


def build_timestamp(day: dt.date, index: int) -> str:
    # Spread same-day commits during working hours.
    hour = 10 + (index % 8)
    minute = (index * 17) % 60
    second = (index * 29) % 60
    return f"{day.isoformat()}T{hour:02d}:{minute:02d}:{second:02d}-0400"


def main():
    parser = argparse.ArgumentParser(description="Moderate deterministic GitHub contribution backfill")
    parser.add_argument("--from", dest="from_date", default="2023-05-25")
    parser.add_argument("--to", dest="to_date", default="2026-05-24")
    parser.add_argument("--max-commits-per-day", type=int, default=3)
    parser.add_argument("--min-active-days-per-week", type=int, default=2)
    parser.add_argument("--max-active-days-per-week", type=int, default=4)
    parser.add_argument("--skip-weeks-rate", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=2608)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--email", default="50302489+Ngenzipack@users.noreply.github.com")
    parser.add_argument("--name", default="Ngenzi")
    parser.add_argument("--activity-file", default="activity.json")
    args = parser.parse_args()

    start_date = parse_date(args.from_date)
    end_date = parse_date(args.to_date)
    if end_date < start_date:
        raise SystemExit("--to must be greater than or equal to --from")

    counts = plan_commits(
        start_date,
        end_date,
        args.min_active_days_per_week,
        args.max_active_days_per_week,
        args.max_commits_per_day,
        args.skip_weeks_rate,
        args.seed,
    )

    total_commits = sum(counts.values())
    active_days = sum(1 for c in counts.values() if c > 0)

    print(f"planned_range={start_date}..{end_date}")
    print(f"planned_active_days={active_days}")
    print(f"planned_total_commits={total_commits}")
    if counts:
        print(f"planned_max_per_day={max(counts.values())}")
    else:
        print("planned_max_per_day=0")

    if args.dry_run:
        top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        print("top_days=")
        for day, c in top:
            print(f"  {day}: {c}")
        return

    repo_root = Path.cwd()
    activity_path = repo_root / args.activity_file
    if not activity_path.exists():
        raise SystemExit(f"activity file not found: {activity_path}")

    run_git(["git", "config", "user.name", args.name], cwd=repo_root)
    run_git(["git", "config", "user.email", args.email], cwd=repo_root)

    sequence = 1
    for day in sorted(counts.keys()):
        for i in range(counts[day]):
            stamp = build_timestamp(day, i)
            write_activity(activity_path, stamp, sequence)
            run_git(["git", "add", args.activity_file], cwd=repo_root)
            env = os.environ.copy()
            env["GIT_AUTHOR_DATE"] = stamp
            env["GIT_COMMITTER_DATE"] = stamp
            run_git(["git", "commit", "-m", f"activity: {stamp}"], cwd=repo_root, env=env)
            sequence += 1

    run_git(["git", "push", "origin", "main"], cwd=repo_root)
    print(f"created_and_pushed_commits={total_commits}")


if __name__ == "__main__":
    main()
