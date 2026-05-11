import time
import requests

API_BASE = "https://intervals.icu/api/v1"

_REQUEST_DELAY = 0.3


def _make_session(api_key):
    session = requests.Session()
    session.auth = ("API_KEY", api_key)
    return session


def _get(session, path, **params):
    resp = session.get(f"{API_BASE}{path}", params=params or None)
    resp.raise_for_status()
    time.sleep(_REQUEST_DELAY)
    return resp.json()


def _extract_hr_zones(detail, act_id):
    """Pull HR zone distribution from an activity detail dict."""
    rows = []

    # intervals.icu stores zones in different shapes depending on version/sport
    candidates = [
        detail.get("icu_zones"),
        detail.get("zones"),
        detail.get("heartrate_zones"),
    ]

    for zone_list in candidates:
        if not zone_list:
            continue
        for idx, z in enumerate(zone_list):
            # Each zone may directly be a bucket (min/max/secs) or a wrapper
            secs = z.get("secs") or z.get("time") or z.get("time_in_zone_s") or 0
            min_hr = z.get("min") or z.get("min_hr") or ""
            max_hr = z.get("max") or z.get("max_hr") or ""
            label = z.get("name") or z.get("id") or f"Z{idx + 1}"
            rows.append({
                "source": "intervals.icu",
                "activity_id": act_id,
                "zone_index": idx + 1,
                "zone_label": label,
                "zone_min_hr": min_hr,
                "zone_max_hr": max_hr,
                "time_in_zone_s": secs,
            })
        return rows  # use the first non-empty candidate

    return rows


def collect(api_key, athlete_id, max_activities=None, log=print):
    log("Connecting to intervals.icu...")
    session = _make_session(api_key)

    # Verify credentials with a lightweight call
    try:
        _get(session, f"/athlete/{athlete_id}")
    except requests.HTTPError as exc:
        if exc.response.status_code == 401:
            raise ValueError("Invalid API key or athlete ID (401 Unauthorized)")
        raise

    log("Fetching activity list...")
    params = {"oldest": "2000-01-01", "newest": "2099-12-31"}
    if max_activities:
        params["limit"] = max_activities
    activities = _get(session, f"/athlete/{athlete_id}/activities", **params)
    log(f"Found {len(activities)} activities")

    all_activities, all_laps, all_zones = [], [], []

    for i, act in enumerate(activities):
        act_id = act.get("id")
        name = act.get("name", str(act_id))
        log(f"[{i+1}/{len(activities)}] {name}")

        try:
            detail = _get(session, f"/activity/{act_id}")
        except requests.HTTPError:
            detail = act

        all_activities.append({
            "source": "intervals.icu",
            "activity_id": act_id,
            "name": detail.get("name", ""),
            "date": detail.get("start_date_local") or detail.get("start_date", ""),
            "sport_type": detail.get("type", ""),
            "distance_m": detail.get("distance", 0),
            "moving_time_s": detail.get("moving_time", 0),
            "elapsed_time_s": detail.get("elapsed_time", 0),
            "avg_speed_ms": detail.get("average_speed", ""),
            "max_speed_ms": detail.get("max_speed", ""),
            "avg_hr": detail.get("average_heartrate", ""),
            "max_hr": detail.get("max_heartrate", ""),
            "elevation_gain_m": detail.get("total_elevation_gain", ""),
        })

        for j, lap in enumerate(detail.get("laps", [])):
            all_laps.append({
                "source": "intervals.icu",
                "activity_id": act_id,
                "lap_index": j + 1,
                "name": lap.get("name", f"Lap {j + 1}"),
                "distance_m": lap.get("distance", 0),
                "elapsed_time_s": lap.get("elapsed_time", 0),
                "moving_time_s": lap.get("moving_time", 0),
                "avg_speed_ms": lap.get("average_speed", ""),
                "max_speed_ms": lap.get("max_speed", ""),
                "avg_hr": lap.get("average_heartrate", ""),
                "max_hr": lap.get("max_heartrate", ""),
            })

        all_zones.extend(_extract_hr_zones(detail, act_id))

    return all_activities, all_laps, all_zones
