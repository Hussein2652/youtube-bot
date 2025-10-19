#!/usr/bin/env python3
"""YouTube resumable uploader with thumbnail support.

Designed to satisfy the local CLI contract documented in the .env example.
"""

import argparse
import json
import os
import sys
import time
from typing import List

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CREDENTIALS_DIR = os.path.join('.', 'credentials')
CLIENT_SECRET = os.path.join(CREDENTIALS_DIR, 'client_secret.json')
TOKEN_PATH = os.path.join(CREDENTIALS_DIR, 'token.json')


def _load_credentials() -> Credentials:
    if not os.path.exists(CLIENT_SECRET):
        raise FileNotFoundError(f"Missing OAuth client secrets: {CLIENT_SECRET}")
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


def _retryable_status(e: Exception) -> bool:
    if isinstance(e, HttpError):
        return e.resp.status in (500, 502, 503, 504)
    return False


def resumable_upload(youtube, args) -> str:
    snippet = {
        'title': args.title,
        'description': args.description,
        'categoryId': args.category,
        'tags': [tag.strip() for tag in args.tags.split(',') if tag.strip()],
    }
    status = {'privacyStatus': args.privacy}
    media = MediaFileUpload(args.file, chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part=','.join(snippet.keys()) + ',status', body={'snippet': snippet, 'status': status}, media_body=media)

    response = None
    retries = 0
    backoff = 1
    while response is None:
        try:
            _, response = request.next_chunk()
            if response is not None:
                if 'id' not in response:
                    raise RuntimeError(f"Upload failed: {response}")
                return response['id']
        except Exception as exc:
            if not _retryable_status(exc):
                raise
            retries += 1
            if retries > 5:
                raise
            time.sleep(backoff)
            backoff = min(backoff * 2, 64)
    raise RuntimeError('Upload produced no response')


def set_thumbnail(youtube, video_id: str, thumb_path: str) -> None:
    if not thumb_path or not os.path.exists(thumb_path):
        return
    media = MediaFileUpload(thumb_path)
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Upload a video to YouTube with thumbnail support')
    parser.add_argument('--file', help='MP4 file path')
    parser.add_argument('--thumb', help='Thumbnail image path')
    parser.add_argument('--title', help='Video title')
    parser.add_argument('--desc', default='', help='Video description')
    parser.add_argument('--tags', default='', help='Comma separated list of tags')
    parser.add_argument('--privacy', default=os.getenv('PRIVACY_STATUS', 'public'), choices=['public', 'unlisted', 'private'])
    parser.add_argument('--category', default=os.getenv('CATEGORY_ID', '24'))
    parser.add_argument('--retry', type=int, default=5)
    parser.add_argument('--auth-only', action='store_true', help='Only perform OAuth flow, no upload')
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    creds = _load_credentials()
    if args.auth_only:
        print(json.dumps({"status": "authenticated"}))
        return 0

    missing = [name for name in ("file", "thumb", "title") if getattr(args, name) is None]
    if missing:
        print(json.dumps({"error": f"Missing required arguments: {', '.join(missing)}"}))
        return 1
    youtube = build('youtube', 'v3', credentials=creds)
    try:
        video_id = resumable_upload(youtube, args)
        set_thumbnail(youtube, video_id, args.thumb)
    except Exception as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({'videoId': video_id}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
