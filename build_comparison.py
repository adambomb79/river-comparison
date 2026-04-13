import json
from datetime import datetime, timedelta
from urllib.request import urlopen
from urllib.parse import urlencode

SITE = "05283500"
PARAM = "00065"


def fetch_json(url: str):
    with urlopen(url, timeout=60) as resp:
        return json.load(resp)


def iv_url(start_date: str, end_date: str) -> str:
    qs = urlencode(
        {
            "format": "json",
            "sites": SITE,
            "parameterCd": PARAM,
            "startDT": start_date,
            "endDT": end_date,
        }
    )
    return f"https://waterservices.usgs.gov/nwis/iv/?{qs}"


def extract_points(data):
    series = data.get("value", {}).get("timeSeries", [])
    points = []
    for s in series:
        vals = s.get("values", [])
        if vals and "value" in vals[0]:
            points.extend(vals[0]["value"])
    return points


def pick_closest_to_midnight_per_day(points):
    grouped = {}

    for p in points:
        dt_raw = p.get("dateTime")
        val_raw = p.get("value")

        if not dt_raw or val_raw in (None, ""):
            continue

        dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
        val = float(val_raw)
        key = dt.strftime("%Y-%m-%d")

        grouped.setdefault(key, []).append((dt, val))

    picked = []

    for _, entries in sorted(grouped.items()):
        sample_date = entries[0][0]
        midnight = sample_date.replace(hour=0, minute=0, second=0, microsecond=0)
        best = min(entries, key=lambda x: abs(x[0] - midnight))
        picked.append(
            {
                "date": best[0].strftime("%Y-%m-%d"),
                "value": best[1],
            }
        )

    return picked


def month_day(date_str: str) -> str:
    return date_str[5:10]


def shift_year_safe(date_obj, years_back):
    try:
        return date_obj.replace(year=date_obj.year - years_back)
    except ValueError:
        # Handles leap day edge case by falling back to Feb 28
        return date_obj.replace(month=2, day=28, year=date_obj.year - years_back)


def main():
    today = datetime.utcnow().date()
    start = today - timedelta(days=13)

    # 14 total days including today
    current_days = [
        (start + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(14)
    ]

    # Buckets keyed by MM-DD
    buckets = {d[5:10]: [] for d in current_days}

    successes = 0
    failures = 0
    window_details = []

    for years_back in (1, 2, 3):
        hist_start = shift_year_safe(start, years_back)
        hist_end = shift_year_safe(today, years_back)

        try:
            url = iv_url(hist_start.isoformat(), hist_end.isoformat())
            data = fetch_json(url)
            points = extract_points(data)
            daily = pick_closest_to_midnight_per_day(points)

            for p in daily:
                md = month_day(p["date"])
                if md in buckets:
                    buckets[md].append(p["value"])

            successes += 1
            window_details.append(
                {
                    "years_back": years_back,
                    "status": "ok",
                    "points": len(points),
                    "daily_points": len(daily),
                    "start": hist_start.isoformat(),
                    "end": hist_end.isoformat(),
                    "url": url,
                }
            )

        except Exception as e:
            failures += 1
            window_details.append(
                {
                    "years_back": years_back,
                    "status": "failed",
                    "error": str(e),
                    "start": hist_start.isoformat(),
                    "end": hist_end.isoformat(),
                }
            )

    labels = [f"{int(d[5:7])}/{int(d[8:10])}" for d in current_days]
    avg = []
    minv = []
    maxv = []

    for d in current_days:
        vals = buckets[d[5:10]]

        if vals:
            avg.append(round(sum(vals) / len(vals), 2))
            minv.append(round(min(vals), 2))
            maxv.append(round(max(vals), 2))
        else:
            avg.append(None)
            minv.append(None)
            maxv.append(None)

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "site": SITE,
        "parameter": PARAM,
        "days": 14,
        "labels": labels,
        "avg": avg,
        "min": minv,
        "max": maxv,
        "successes": successes,
        "failures": failures,
        "window_details": window_details,
    }

    with open("comparison.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("Wrote comparison.json")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
