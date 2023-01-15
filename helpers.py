from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

import urllib.parse

import json

from functools import wraps

from pathlib import Path

from wistia import WistiaClient


def find_smallest_video_asset_url(wistia: WistiaClient, wistia_hashed_id: str):
    media = wistia.show_media(wistia_hashed_id)
    video_assets = [a for a in media.assets if a.content_type == 'video/mp4']
    smallest_video = sorted(video_assets, key=lambda v: v.file_size)[0]
    return smallest_video.url


def cache_as_json(filename_pattern):
    """
    Function decorator that will cache the result as a local json file
    Very handy for HTTP requests for web crawlers etc.

    Usage:

    @cache_as_json(filename_pattern="my_func__{my_kwarg}.json")
    def my_func(*args, my_kwarg='', **kwargs):
        ...
    """
    folder = Path("./cache/")
    folder.mkdir(exist_ok=True)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            sanitized_kwargs = {
                key: urllib.parse.quote(value) if isinstance(value, str) else value
                for key, value in kwargs.items()
            }
            file_path = folder / filename_pattern.format(**sanitized_kwargs)
            try:
                with file_path.open("r", encoding="utf-8") as f:
                    value = json.load(f)
            except FileNotFoundError:
                value = func(*args, **kwargs)
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(value, f, ensure_ascii=False, indent=2)

            return value

        return wrapper

    return decorator
