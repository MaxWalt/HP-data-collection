#!/usr/bin/env python3
"""
One-time helper to get a Strava refresh token.

Steps:
  1. Create a Strava API app at https://www.strava.com/settings/api
     Set "Authorization Callback Domain" to: localhost
  2. Run:  python strava_auth.py
  3. Open the printed URL in your browser, authorize, then paste the
     redirect URL (or just the 'code' query param) back here.
  4. Copy the printed STRAVA_REFRESH_TOKEN into your .env file.
"""

import sys
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs

TOKEN_URL = "https://www.strava.com/oauth/token"
AUTH_URL = "https://www.strava.com/oauth/authorize"


def main():
    client_id = input("Enter your Strava Client ID: ").strip()
    client_secret = input("Enter your Strava Client Secret: ").strip()

    auth_url = (
        f"{AUTH_URL}?client_id={client_id}"
        "&response_type=code"
        "&redirect_uri=http://localhost"
        "&approval_prompt=force"
        "&scope=activity:read_all"
    )

    print(f"\nOpen this URL in your browser:\n\n  {auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    raw = input(
        "After authorizing, paste the full redirect URL (or just the 'code' value): "
    ).strip()

    if raw.startswith("http"):
        qs = parse_qs(urlparse(raw).query)
        code = qs.get("code", [None])[0]
        if not code:
            sys.exit("Could not find 'code' in the URL. Try pasting just the code value.")
    else:
        code = raw

    resp = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    })

    if not resp.ok:
        sys.exit(f"Token exchange failed: {resp.status_code} {resp.text}")

    data = resp.json()
    refresh_token = data.get("refresh_token")
    athlete = data.get("athlete", {})

    print(f"\nSuccess! Authenticated as: {athlete.get('firstname')} {athlete.get('lastname')}")
    print("\nAdd these to your .env file:")
    print(f"  STRAVA_CLIENT_ID={client_id}")
    print(f"  STRAVA_CLIENT_SECRET={client_secret}")
    print(f"  STRAVA_REFRESH_TOKEN={refresh_token}")


if __name__ == "__main__":
    main()
