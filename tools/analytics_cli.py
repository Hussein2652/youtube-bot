#!/usr/bin/env python3
"""Fetch basic YouTube analytics for a video.

Environment:
  YOUTUBE_CLIENT_SECRETS_FILE
  YOUTUBE_TOKEN_FILE (optional, default data/youtube_token.json)
  YOUTUBE_CHANNEL_ID

Usage:
  python tools/analytics_cli.py --video-id <ID> --start-date 2024-01-01 --end-date 2024-01-02

Prints JSON with impressions, ctr, avg_view_pct, avg_view_sec, likes.
"""

import argparse
import json
import os
import sys

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _load_credentials(client_secrets: str, token_path: str) -> Credentials:
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes=SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
            creds = flow.run_console()
        with open(token_path, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())
    return creds


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Fetch YouTube analytics metrics for a video')
    parser.add_argument('--video-id', required=True)
    parser.add_argument('--start-date', required=True, help='YYYY-MM-DD')
    parser.add_argument('--end-date', required=True, help='YYYY-MM-DD')
    return parser.parse_args(argv)


def main(argv=None):
    argv = argv or sys.argv[1:]
    args = parse_args(argv)
    channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    if not channel_id:
        raise SystemExit('YOUTUBE_CHANNEL_ID missing')
    secrets = os.getenv('YOUTUBE_CLIENT_SECRETS_FILE')
    if not secrets or not os.path.exists(secrets):
        raise SystemExit('YOUTUBE_CLIENT_SECRETS_FILE missing')
    token_file = os.getenv('YOUTUBE_TOKEN_FILE', 'data/youtube_token.json')
    os.makedirs(os.path.dirname(token_file), exist_ok=True)

    creds = _load_credentials(secrets, token_file)
    analytics = build('youtubeAnalytics', 'v2', credentials=creds)

    report = analytics.reports().query(
        ids=f'channel=={channel_id}',
        filters=f'video=={args.video_id}',
        startDate=args.start_date,
        endDate=args.end_date,
        metrics='impressions,impressionsCtr,averageViewDuration,averageViewPercentage,likes',
        dimensions='video',
    ).execute()

    rows = report.get('rows') or []
    if not rows:
        print(json.dumps({'videoId': args.video_id, 'metrics': None}))
        return
    values = rows[0]
    data = {
        'videoId': args.video_id,
        'impressions': values[1],
        'ctr': values[2],
        'avg_view_duration_sec': values[3],
        'avg_view_percent': values[4],
        'likes': values[5],
    }
    print(json.dumps(data))


if __name__ == '__main__':
    main()

