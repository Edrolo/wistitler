#!/usr/bin/env python
from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

import argparse
import logging
import multiprocessing
import sys
import urllib
from contextlib import contextmanager
from functools import wraps
from time import time

from six.moves import urllib

import nlpcloud_service
from helpers import find_smallest_video_asset_url

from wistia import (
    WistiaClient,
    get_wistia_client,
)

import autosub

logger = logging.getLogger(__name__)


@contextmanager
def terminating(thing):
    """Allow multiprocessing.Pool() to be used as a context manager in Python 2"""
    try:
        yield thing
    finally:
        thing.terminate()


def timing(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        start_time = time()
        result = f(*args, **kwargs)
        end_time = time()
        logger.info('func:%r args:[%r, %r] took: %2.4f sec' %
                    (f.__name__, args, kwargs, end_time - start_time))
        return result

    return wrap


def find_smallest_video_asset_url(wistia: WistiaClient, wistia_hashed_id: str):
    media = wistia.show_media(wistia_hashed_id)
    video_assets = [a for a in media.assets if a.content_type == 'video/mp4']
    smallest_video = sorted(video_assets, key=lambda v: v.file_size)[0]
    return smallest_video.url


@timing
def caption_project(
    project_hashed_id,
    replace=False,
    wistia: WistiaClient = None,
    captioning_service="whisper",
):
    wistia = wistia or get_wistia_client()
    project = wistia.show_project(project_hashed_id)
    logger.info(f'"{project.name}" [{project.hashed_id}] has {project.media_count} media')
    logger.info("Gonna captch 'em all!")
    media_list = project.medias

    # concurrency = 10
    # with terminating(multiprocessing.Pool(processes=concurrency)) as pool:
    #     results = [
    #         pool.apply_async(
    #             subtitle_wistia_video,
    #             kwds=dict(
    #                 wistia_hashed_id=media_item.hashed_id,
    #                 replace=replace,
    #             ),
    #         ) for media_item in media_list
    #     ]
    #     completed_subtitles = [p.get() for p in results]
    #
    #

    # Serial version
    completed_subtitles = [
        subtitle_wistia_video(
            wistia_hashed_id=media_item.hashed_id,
            replace=replace,
            captioning_service=captioning_service,
        )
        for media_item in media_list
    ]

    return completed_subtitles


def enable_captions_for_project(
    project_hashed_id: str,
    enabled: bool = True,
    wistia: WistiaClient = None,
):
    wistia = wistia or get_wistia_client()
    project = wistia.show_project(project_hashed_id)
    logger.info(
        f'"{project.name}" [{project.hashed_id}] has {project.media_count} media'
    )
    logger.info(f'{"En" if enabled else "Dis"}abling captions...')
    media_list = project.medias

    concurrency = 10
    with terminating(multiprocessing.Pool(processes=concurrency)) as pool:
        results = [
            pool.apply_async(
                wistia.enable_captions_for_media,
                kwds=dict(
                    wistia_hashed_id=media_item.hashed_id,
                    enabled=enabled,
                ),
            )
            for media_item in media_list
        ]
        modified_media_customizations = [p.get() for p in results]

    return modified_media_customizations


def download_file(file_url):
    filename, headers = urllib.request.urlretrieve(file_url)
    return filename


def autosub_video_file(video_file_name, **extra_options):
    srt_file_name = autosub.generate_subtitle_file(
        source_path=video_file_name, **extra_options
    )
    return srt_file_name


def get_media_url(media_hashed_id: str) -> str:
    return f"https://my.wistia.com/medias/{media_hashed_id}"


def get_project_url(project_hashed_id: str) -> str:
    return f"https://my.wistia.com/projects/{project_hashed_id}"


def autosub_generate_subtitles_for_video_at_url(
    video_file_url, service_options=None, **kwargs
):
    """Callable func for autosub (which includes Google API)"""
    logger.info("Autosub: Downloading video")
    service_options = service_options or {}
    video_file_name = download_file(video_file_url)
    logger.debug(f"Autosub: Downloaded file to {video_file_name}")
    logger.info("Autosub: Feeding video to autosub")
    # Can raise google.api_core.exceptions.ResourceExhausted (429)
    subtitle_file_name = autosub_video_file(video_file_name, **service_options)
    logger.info(f"Autosub: Generated subtitle file: {subtitle_file_name}")
    return subtitle_file_name


captioning_services = {
    "autosub": autosub_generate_subtitles_for_video_at_url,
    "whisper": nlpcloud_service.generate_subtitles_for_video_at_url,
}


@timing
def subtitle_wistia_video(
    wistia_hashed_id: str,
    replace=False,
    wistia: WistiaClient = None,
    captioning_service="whisper",
    **kwargs,
):
    wistia = wistia or get_wistia_client()
    captioning_service_func = captioning_services.get(captioning_service)

    logger.info(f'Wistia hashed id: {wistia_hashed_id}')
    video_url = get_media_url(wistia_hashed_id)

    logger.info('Fetching video info')
    # Can raise requests.exceptions.HTTPError (503)
    video_file_url = find_smallest_video_asset_url(wistia, wistia_hashed_id)
    logger.debug(f'Found smallest video asset url: {video_file_url}')

    subtitle_file_name, srt_file = captioning_service_func(
        url=video_file_url,
        key=wistia_hashed_id,
    )

    # Can raise requests.exceptions.HTTPError (503)
    logger.info('Uploading subtitle file to wistia')
    wistia.upload_subtitle_file_to_wistia_video(
        wistia_hashed_id,
        subtitle_file_name,
        replace=replace,
    )

    logger.info('Done!')
    logger.info(f'Check out the subtitles at: {video_url}')

    return video_url


def main():
    try:
        args = parse_arguments()

        video_hashed_id = args.video
        project_hashed_id = args.project
        list_projects = args.list_projects
        replace = args.replace
        toggle_captions = bool(args.toggle_captions)
        set_captions_to = args.toggle_captions.lower() == "on"
        captioning_service = args.service

        wistia = get_wistia_client(args.password or None)

        logging.basicConfig(
            level=args.loglevel,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )

        if list_projects:
            projects = sorted(wistia.list_all_projects(), key=lambda p: p['name'])
            for index, project in enumerate(projects):
                print('{}. {hashedId}: {name}'.format(index, **project))

        elif project_hashed_id:
            if toggle_captions:
                enable_captions_for_project(project_hashed_id, enabled=set_captions_to)
            else:
                caption_project(project_hashed_id, replace=replace)

        elif video_hashed_id:
            if toggle_captions:
                wistia.enable_captions_for_media(video_hashed_id, enabled=set_captions_to)
            else:
                subtitle_wistia_video(video_hashed_id, replace=replace)

    except KeyboardInterrupt:
        logger.error('Program interrupted!')
    finally:
        logging.shutdown()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "A tool for automatically generating and adding captions "
            "to Wistia videos and projects. "
            "Make sure you have `WISTIA_API_PASSWORD` set in your environment."
        ), )
    parser.add_argument(
        '-d',
        '--debug',
        help='Print lots of debugging statements',
        action='store_const',
        dest='loglevel',
        const=logging.DEBUG,
        default=logging.WARN,
    )
    parser.add_argument(
        '--verbose',
        help='Be verbose',
        action='store_const',
        dest='loglevel',
        const=logging.INFO,
    )
    parser.add_argument(
        '-r',
        '--replace',
        help='Replace existing captions if present',
        action='store_true',
    )
    parser.add_argument(
        '-t',
        '--toggle-captions',
        type=str,
        choices=('on', 'off', 'ON', 'OFF'),
        default='',
        help='Turn captions on or off',
        action='store',
    )
    parser.add_argument(
        '--password',
        type=str,
        default="",
        help="Wistia API password",
        action="store",
    )
    parser.add_argument(
        "--service",
        type=str,
        choices=list(captioning_services.keys()),
        default="whisper",
        help="Captioning service to use",
        action="store",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-v',
        '--video',
        help='Hashed ID of video to caption',
    )
    group.add_argument(
        '-p',
        '--project',
        help='Caption all videos in project with given hashed_id',
    )
    group.add_argument(
        '-l',
        '--list-projects',
        help='Print a list of all projects in your Wistia account',
        action='store_true',
    )
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    sys.exit(main())
