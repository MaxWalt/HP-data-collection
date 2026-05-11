import time
import requests

TOKEN_URL = "https://www.strava.com/oauth/token"
API_BASE = "https://www.strava.com/api/v3"

# Strava rate limit: 100 requests/15 min, 1000/day
_REQUEST_DELAY = 0.5


def _get_access_token(client_id, client_secret, refresh_token):
    resp = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def _get(session, path, **params):
    resp = session.get(f"{API_BASE}{path}", params=params or None)
    resp.raise_for_status()
    time.sleep(_REQUEST_DELAY)
    return resp.json()


def _fetch_all_activities(session, max_activities):
    activities = []
    page = 1
    while True:
        batch = _get(session, "/athlete/activities", per_page=100, page=page)
        if not batch:
            break
        activities.extend(batch)
        if max_activities and len(activities) >= max_activities:
            return activities[:max_activities]
        if len(batch) < 100:
            break
        page += 1
    return activities


def collect(client_id, client_secret, refresh_token, max_activities=None):
    print("Authenticating with Strava...")
    token = _get_access_token(client_id, client_secret, refresh_token)

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"

    print("Fetching activity list...")
    activities = _fetch_all_activities(session, max_activities)
    print(f"Found {len(activities)} activities")

    all_activities, all_laps, all_zones = [], [], []

    for i, act in enumerate(activities):
        act_id = act["id"]
        name = act.get("name", str(act_id))
        print(f"  [{i+1}/{len(activities)}] {name}")

        detail = _get(session, f"/activities/{act_id}")

        all_activities.append({
            "source": "strava",
            "activity_id": act_id,
            "name": detail.get("name", ""),
            "date": detail.get("start_date_local", ""),
            "sport_type": detail.get("sport_type") or detail.get("type", ""),
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
                "source": "strava",
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

        try:
            zones_data = _get(session, f"/activities/{act_id}/zones")
            for zone_block in zones_data:
                if zone_block.get("type") == "heartrate":
                    for idx, bucket in enumerate(zone_block.get("distribution_buckets", [])):
                        all_zones.append({
                            "source": "strava",
                            "activity_id": act_id,
                            "zone_index": idx + 1,
                            "zone_min_hr": bucket.get("min", ""),
                            "zone_max_hr": bucket.get("max", ""),
                            "time_in_zone_s": bucket.get("time", 0),
                        })
        except requests.HTTPError as exc:
            if exc.response.status_code not in (404, 401):
                raise
            # Activity has no zone data (no HR monitor or free account limit)

    return all_activities, all_laps, all_zones
