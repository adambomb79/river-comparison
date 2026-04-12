import json
from datetime import datetime, timedelta
from urllib.request import urlopen
from urllib.parse import urlencode

SITE = "05283500"
PARAM = "00065"

def fetch_json(url: str):
    with urlopen(url) as resp:
        return json.load(resp)

def iv_url(start_date: str, end_date: str) -> str:
    qs = urlencode({
        "format": "json",
        "sites": SITE,
        "parameterCd": PARAM,
        "startDT": start_date,
        "endDT": end_date,
    })
    return f"https://waterservices.usgs.gov/nwis/iv/?{qs}"

def pick_closest_to_midnight_per_day(points):
    grouped = {}
    for p in points:
        dt = datetime.fromisoformat(p["dateTime"].replace("Z", "+00:00"))
        key = dt.strftime("%Y-%m-%d")
        grouped.setdefault(key, []).append((dt, float(p["value"])))

    picked = []
    for _, entries in sorted(grouped.items()):
        sample_date = entries[0][0]
        midnight = sample_date.replace(hour=0, minute=0, second=0, microsecond=0)
        best = min(entries, key=lambda x: abs(x[0] - midnight))
        picked.append({"date": best[0].strftime("%Y-%m-%d"), "value": best[1]})
    return picked

def month_day(date_str: str) -> str:
    return date_str[5:10]

def main():
    today = datetime.utcnow().date()
    start = today - timedelta(days=6)

    current_days = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    buckets = {d[5:10]: [] for d in current_days}

    successes = 0
    failures = 0

    for years_back in (1, 2, 3):
        hist_start = start.replace(year=start.year - years_back)
        hist_end = today.replace(year=today.year - years_back)

        try:
            data = fetch_json(iv_url(hist_start.isoformat(), hist_end.isoformat()))
            ts = data.get("value", {}).get("timeSeries", [])
            points = []
            for series in ts:
                points.extend(series.get("values", [{}])[0].get("value", []))

            daily = pick_closest_to_midnight_per_day(points)
            for p in daily:
                md = month_day(p["date"])
                if md in buckets:
                    buckets[md].append(p["value"])
            successes += 1
        except Exception:
            failures += 1

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
        "labels": labels,
        "avg": avg,
        "min": minv,
        "max": maxv,
        "successes": successes,
        "failures": failures,
    }

    with open("comparison.json", "w") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    main()
