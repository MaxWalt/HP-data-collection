#!/usr/bin/env python3
"""
Streamlit UI for the training data collector.

Run with:
  streamlit run app.py
"""

import io
import os
import csv

import requests
import streamlit as st
from dotenv import load_dotenv

import strava
import intervals

load_dotenv()

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

ACTIVITY_FIELDS = [
    "source", "activity_id", "name", "date", "sport_type",
    "distance_m", "moving_time_s", "elapsed_time_s",
    "avg_speed_ms", "max_speed_ms", "avg_hr", "max_hr", "elevation_gain_m",
]
LAP_FIELDS = [
    "source", "activity_id", "lap_index", "name",
    "distance_m", "elapsed_time_s", "moving_time_s",
    "avg_speed_ms", "max_speed_ms", "avg_hr", "max_hr",
]
ZONE_FIELDS = [
    "source", "activity_id", "zone_index", "zone_label",
    "zone_min_hr", "zone_max_hr", "time_in_zone_s",
]

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Training Data Collector", page_icon="🏃", layout="wide")
st.title("🏃 Training Data Collector")
st.caption("Pull session data from Strava and/or intervals.icu into downloadable CSVs.")

# ── Strava OAuth callback ─────────────────────────────────────────────────────
query = st.query_params
if "code" in query and "strava_refresh_token" not in st.session_state:
    code = query["code"]
    cid  = st.session_state.get("strava_client_id", "")
    csec = st.session_state.get("strava_client_secret", "")
    if cid and csec:
        with st.spinner("Completing Strava authorization..."):
            resp = requests.post(STRAVA_TOKEN_URL, data={
                "client_id": cid,
                "client_secret": csec,
                "code": code,
                "grant_type": "authorization_code",
            })
        if resp.ok:
            data = resp.json()
            st.session_state["strava_refresh_token"] = data["refresh_token"]
            athlete = data.get("athlete", {})
            st.session_state["strava_athlete"] = (
                f"{athlete.get('firstname','')} {athlete.get('lastname','')}".strip()
            )
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"Strava authorization failed: {resp.text}")
    else:
        st.warning(
            "Enter your Strava **Client ID** and **Client Secret** in the sidebar, "
            "then click **Connect with Strava** again."
        )

# ── Sidebar: credentials ──────────────────────────────────────────────────────
with st.sidebar:
    # ── Strava ────────────────────────────────────────────────────────────────
    st.header("Strava")

    client_id = st.text_input(
        "Client ID",
        value=st.session_state.get("strava_client_id", os.environ.get("STRAVA_CLIENT_ID", "")),
    )
    client_secret = st.text_input(
        "Client Secret",
        type="password",
        value=st.session_state.get("strava_client_secret", os.environ.get("STRAVA_CLIENT_SECRET", "")),
    )

    # Persist so the OAuth callback can read them after redirect
    if client_id:
        st.session_state["strava_client_id"] = client_id
    if client_secret:
        st.session_state["strava_client_secret"] = client_secret

    if "strava_refresh_token" in st.session_state:
        athlete_name = st.session_state.get("strava_athlete", "Strava user")
        st.success(f"Connected as **{athlete_name}**")
        if st.button("Disconnect Strava"):
            st.session_state.pop("strava_refresh_token", None)
            st.session_state.pop("strava_athlete", None)
            st.rerun()
        refresh_token = st.session_state["strava_refresh_token"]
    else:
        refresh_token = st.text_input(
            "Refresh Token",
            type="password",
            value=os.environ.get("STRAVA_REFRESH_TOKEN", ""),
            help="Run `python strava_auth.py` once in a terminal to get this value.",
        )
        if client_id and client_secret:
            auth_url = (
                "https://www.strava.com/oauth/authorize"
                f"?client_id={client_id}"
                "&response_type=code"
                "&redirect_uri=http://localhost:8501"
                "&approval_prompt=force"
                "&scope=activity:read_all"
            )
            st.link_button("1 · Authorize on Strava", auth_url, use_container_width=True)
            st.caption(
                "After clicking Authorize, your browser will show an error page — "
                "that's normal. **Copy the full URL** from the address bar and paste it below."
            )
            pasted = st.text_input("2 · Paste the redirect URL here", key="pasted_url")
            if pasted:
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(pasted).query)
                code = qs.get("code", [None])[0]
                if code:
                    with st.spinner("Exchanging code for token..."):
                        resp = requests.post(STRAVA_TOKEN_URL, data={
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "code": code,
                            "grant_type": "authorization_code",
                        })
                    if resp.ok:
                        data = resp.json()
                        st.session_state["strava_refresh_token"] = data["refresh_token"]
                        athlete = data.get("athlete", {})
                        st.session_state["strava_athlete"] = (
                            f"{athlete.get('firstname','')} {athlete.get('lastname','')}".strip()
                        )
                        st.rerun()
                    else:
                        st.error(f"Token exchange failed: {resp.text}")
                else:
                    st.error("Could not find a 'code' in that URL. Make sure you copied the full address bar URL.")
        else:
            st.info("Enter Client ID and Secret to enable Strava login.")

    st.divider()

    # ── intervals.icu ─────────────────────────────────────────────────────────
    st.header("intervals.icu")
    icu_key = st.text_input(
        "API Key",
        type="password",
        value=os.environ.get("INTERVALS_API_KEY", ""),
        help="Settings → Developer Settings on intervals.icu",
    )
    icu_athlete = st.text_input(
        "Athlete ID",
        value=os.environ.get("INTERVALS_ATHLETE_ID", ""),
        help="The iXXXXX in your profile URL, e.g. i12345",
    )

# ── Main: collection options ──────────────────────────────────────────────────
st.subheader("Collection settings")

col_src, col_max = st.columns([2, 1])
with col_src:
    source = st.radio(
        "Data source",
        ["Both", "Strava only", "intervals.icu only"],
        horizontal=True,
    )
with col_max:
    max_act = st.number_input(
        "Max activities (0 = all)",
        min_value=0,
        value=0,
        step=10,
        help="Set to a small number (e.g. 5) to test your credentials before a full pull.",
    )

# Decide whether the button should be enabled
need_strava = source in ("Both", "Strava only")
need_icu    = source in ("Both", "intervals.icu only")
has_strava  = bool(client_id and client_secret and refresh_token)
has_icu     = bool(icu_key and icu_athlete)

missing = []
if need_strava and not has_strava:
    missing.append("Strava credentials")
if need_icu and not has_icu:
    missing.append("intervals.icu credentials")

if missing:
    st.info(f"Fill in {' and '.join(missing)} in the sidebar to get started.")

if st.button("Collect Data", type="primary", disabled=bool(missing)):
    max_n = max_act if max_act > 0 else None
    acts, laps, zones = [], [], []
    ok = True

    with st.status("Collecting data...", expanded=True) as status:
        if need_strava:
            st.write("**Strava** — connecting...")
            try:
                a, l, z = strava.collect(
                    client_id, client_secret, refresh_token,
                    max_activities=max_n,
                    log=st.write,
                )
                acts.extend(a); laps.extend(l); zones.extend(z)
                st.write(f"✅ Strava done: {len(a)} activities, {len(l)} laps, {len(z)} zone rows")
            except Exception as exc:
                st.error(f"Strava error: {exc}")
                ok = False

        if need_icu:
            st.write("**intervals.icu** — connecting...")
            try:
                a, l, z = intervals.collect(
                    icu_key, icu_athlete,
                    max_activities=max_n,
                    log=st.write,
                )
                acts.extend(a); laps.extend(l); zones.extend(z)
                st.write(f"✅ intervals.icu done: {len(a)} activities, {len(l)} laps, {len(z)} zone rows")
            except Exception as exc:
                st.error(f"intervals.icu error: {exc}")
                ok = False

        if ok:
            st.session_state["data"] = {"activities": acts, "laps": laps, "zones": zones}
            status.update(label="Done!", state="complete")
        else:
            status.update(label="Finished with errors.", state="error")

# ── Results ───────────────────────────────────────────────────────────────────
if "data" in st.session_state:
    data = st.session_state["data"]
    acts  = data["activities"]
    laps  = data["laps"]
    zones = data["zones"]

    def _to_csv(rows, fields):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    st.divider()
    st.subheader("Results")

    tab_acts, tab_laps, tab_zones = st.tabs(
        [f"Activities ({len(acts)})", f"Laps ({len(laps)})", f"HR Zones ({len(zones)})"]
    )

    with tab_acts:
        st.download_button(
            "Download activities.csv",
            data=_to_csv(acts, ACTIVITY_FIELDS),
            file_name="activities.csv",
            mime="text/csv",
        )
        if acts:
            import pandas as pd
            df = pd.DataFrame(acts)[ACTIVITY_FIELDS]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No activities collected.")

    with tab_laps:
        st.download_button(
            "Download laps.csv",
            data=_to_csv(laps, LAP_FIELDS),
            file_name="laps.csv",
            mime="text/csv",
        )
        if laps:
            import pandas as pd
            df = pd.DataFrame(laps)[LAP_FIELDS]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No lap data collected.")

    with tab_zones:
        st.download_button(
            "Download hr_zones.csv",
            data=_to_csv(zones, ZONE_FIELDS),
            file_name="hr_zones.csv",
            mime="text/csv",
        )
        if zones:
            import pandas as pd
            df = pd.DataFrame(zones)[ZONE_FIELDS]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No HR zone data collected.")
