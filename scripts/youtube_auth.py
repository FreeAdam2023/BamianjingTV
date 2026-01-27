#!/usr/bin/env python3
"""
One-time script to generate YouTube OAuth token.

Run this script locally (not in Docker) to authorize YouTube access:

    python scripts/youtube_auth.py

This will:
1. Open a browser for Google OAuth
2. Save the token to credentials/youtube_token.pickle
"""

import pickle
from pathlib import Path

def main():
    credentials_file = Path("credentials/youtube_oauth.json")
    token_file = Path("credentials/youtube_token.pickle")

    if not credentials_file.exists():
        print(f"Error: {credentials_file} not found!")
        print("Please download OAuth client credentials from Google Cloud Console.")
        return

    # Import Google libraries
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        print("Missing dependencies. Install with:")
        print("  pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        return

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]

    credentials = None

    # Load existing token if available
    if token_file.exists():
        with open(token_file, "rb") as f:
            credentials = pickle.load(f)
        print(f"Loaded existing token from {token_file}")

    # Refresh or get new token
    if credentials and credentials.expired and credentials.refresh_token:
        print("Token expired, refreshing...")
        credentials.refresh(Request())
    elif not credentials or not credentials.valid:
        print("Starting OAuth flow...")
        print("A browser window will open for authorization.")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_file),
            scopes=SCOPES,
        )
        credentials = flow.run_local_server(port=8080)

    # Save the token
    with open(token_file, "wb") as f:
        pickle.dump(credentials, f)

    print(f"\n✅ Token saved to {token_file}")
    print("You can now upload videos to YouTube!")

    # Test the token
    try:
        from googleapiclient.discovery import build
        service = build("youtube", "v3", credentials=credentials)
        response = service.channels().list(part="snippet", mine=True).execute()

        if response.get("items"):
            channel = response["items"][0]
            print(f"\n📺 Authorized for channel: {channel['snippet']['title']}")
        else:
            print("\n⚠️ No YouTube channel found for this account")
    except Exception as e:
        print(f"\n⚠️ Could not verify channel: {e}")

if __name__ == "__main__":
    main()
