#!/usr/bin/env python3
"""Resumable YouTube upload CLI with thumbnail support.

Environment variables:
  YOUTUBE_CLIENT_SECRETS_FILE: path to OAuth client secrets JSON.
  YOUTUBE_TOKEN_FILE: path to store OAuth tokens (default: data/youtube_token.json).

Usage:
  python tools/uploader_cli.py --file path.mp4 --thumbnail thumb.png --title "Title" --description "desc"

Outputs JSON: {"videoId": "...", "status": "uploaded"}
"""

import argparse
import json
import os
import sys
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


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


def resumable_upload(youtube, options):
    body = {
        'snippet': {
            'title': options.title,
            'description': options.description,
            'categoryId': options.category_id,
            'tags': options.tags,
        },
        'status': {
            'privacyStatus': options.privacy_status,
        },
    }

    media = MediaFileUpload(options.file, chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)

    response = None
    error = None
    retry = 0
    backoff = 1
    while response is None:
        try:
            status, response = request.next_chunk()
            if response is not None:
                if 'id' in response:
                    return response['id']
                raise RuntimeError(f"Upload failed: {response}")
            if status:
                print(f"Upload {int(status.progress() * 100)}%", file=sys.stderr)
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                error = e
            else:
                raise
        except Exception as e:  # noqa
            error = e

        if error:
            retry += 1
            if retry > 5:
                raise error
            sleep_time = backoff
            backoff = min(backoff * 2, 64)
            print(f"Retry {retry} after error {error}, sleeping {sleep_time}s", file=sys.stderr)
            time.sleep(sleep_time)
            error = None


def set_thumbnail(youtube, video_id: str, thumbnail_path: str) -> None:
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        return
    media = MediaFileUpload(thumbnail_path)
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Upload a video to YouTube with thumbnail")
    parser.add_argument('--file', required=True, help='Video file path')
    parser.add_argument('--thumbnail', help='Thumbnail image path')
    parser.add_argument('--title', required=True, help='Video title')
    parser.add_argument('--description', default='', help='Video description')
    parser.add_argument('--category-id', default='24', help='YouTube category id (default: 24 = Entertainment)')
    parser.add_argument('--tags', nargs='*', default=[], help='Space separated list of tags')
    parser.add_argument('--privacy-status', default='public', choices=['public', 'unlisted', 'private'])
    return parser.parse_args(argv)


def main(argv=None):
    argv = argv or sys.argv[1:]
    opts = parse_args(argv)
    client_secrets = os.getenv('YOUTUBE_CLIENT_SECRETS_FILE')
    if not client_secrets or not os.path.exists(client_secrets):
        raise SystemExit('YOUTUBE_CLIENT_SECRETS_FILE not set or missing.')
    token_file = os.getenv('YOUTUBE_TOKEN_FILE', 'data/youtube_token.json')
    os.makedirs(os.path.dirname(token_file), exist_ok=True)

    creds = _load_credentials(client_secrets, token_file)
    youtube = build('youtube', 'v3', credentials=creds)

    video_id = resumable_upload(youtube, opts)
    set_thumbnail(youtube, video_id, opts.thumbnail)

    print(json.dumps({'videoId': video_id, 'status': 'uploaded'}))


if __name__ == '__main__':
    main()

