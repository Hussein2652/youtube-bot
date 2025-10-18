#!/usr/bin/env python3
"""Fetch recent YouTube analytics metrics and write to JSON."""

import argparse
import datetime as dt
import json
import os
import sys
from typing import List

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CREDENTIALS_DIR = os.path.join('.', 'credentials')
CLIENT_SECRET = os.path.join(CREDENTIALS_DIR, 'client_secret.json')
TOKEN_PATH = os.path.join(CREDENTIALS_DIR, 'token.json')


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Pull recent YouTube analytics metrics')
    parser.add_argument('--since', default='2d', help='Look-back window (e.g., 2d, 72h, 7d)')
    parser.add_argument('--out', required=True, help='Output JSON path')
    parser.add_argument('--video-ids', nargs='*', help='Optional explicit video ids')
    return parser.parse_args(argv)


def parse_since(since: str) -> dt.date:
    since = since.strip().lower()
    if since.endswith('d'):
        days = int(since[:-1])
        return (dt.datetime.utcnow() - dt.timedelta(days=days)).date()
    if since.endswith('h'):
        hours = int(since[:-1])
        return (dt.datetime.utcnow() - dt.timedelta(hours=hours)).date()
    raise ValueError('Unsupported interval format. Use e.g. 2d or 72h')


def load_credentials() -> Credentials:
    if not os.path.exists(CLIENT_SECRET):
        raise FileNotFoundError(f"Missing OAuth credentials at {CLIENT_SECRET}")
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_console()
        with open(TOKEN_PATH, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())
    return creds


def fetch_metrics(analytics, channel_id: str, video_ids: List[str], start_date: dt.date, end_date: dt.date) -> List[dict]:
    metrics = []
    for vid in video_ids:
        report = analytics.reports().query(
            ids=f'channel=={channel_id}',
            filters=f'video=={vid}',
            startDate=start_date.isoformat(),
            endDate=end_date.isoformat(),
            metrics='impressions,impressionsCtr,averageViewDuration,averageViewPercentage,likes',
            dimensions='video',
        ).execute()
        rows = report.get('rows') or []
        if not rows:
            continue
        row = rows[0]
        metrics.append({
            'videoId': vid,
            'impressions': row[1],
            'ctr': row[2],
            'avg_view_pct': row[4],
            'avg_view_duration': row[3],
            'like_rate': row[5] / row[1] if row[1] else 0.0,
        })
    return metrics


def list_recent_videos(youtube) -> List[str]:
    uploads = youtube.channels().list(part='contentDetails', mine=True).execute()
    items = uploads.get('items') or []
    if not items:
        return []
    upload_playlist = items[0]['contentDetails']['relatedPlaylists']['uploads']
    playlist_items = youtube.playlistItems().list(part='contentDetails', playlistId=upload_playlist, maxResults=50).execute()
    vids = []
    for entry in playlist_items.get('items', []):
        vids.append(entry['contentDetails']['videoId'])
    return vids


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    since_date = parse_since(args.since)
    end_date = dt.datetime.utcnow().date()

    channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    if not channel_id:
        print(json.dumps({'error': 'YOUTUBE_CHANNEL_ID not set'}), file=sys.stderr)
        return 1

    creds = load_credentials()
    youtube = build('youtube', 'v3', credentials=creds)
    analytics = build('youtubeAnalytics', 'v2', credentials=creds)

    video_ids = args.video_ids or list_recent_videos(youtube)
    if not video_ids:
        print(json.dumps({'error': 'No video ids available'}), file=sys.stderr)
        return 1

    data = fetch_metrics(analytics, channel_id, video_ids, since_date, end_date)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
