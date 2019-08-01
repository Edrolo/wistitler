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
from os import environ
from time import time

import requests
from six.moves import urllib

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


class WistiaClient:
    def __init__(self, api_password):
        self.session = requests.Session()
        self.session.auth = ('api', api_password)

    def list_all_projects(self):
        logger.info('Listing all projects')
        projects_url = 'https://api.wistia.com/v1/projects.json'
        projects_list = []
        for page in range(1, 21):
            next_page_response = self.session.get('{}?page={}'.format(
                projects_url, page))
            next_page_response.raise_for_status()
            next_page_of_projects = next_page_response.json()
            if next_page_of_projects:
                projects_list += next_page_of_projects
            else:
                break
        else:
            logger.warning(
                'More than 2000 Wistia projects! Might need to increase limits in code'
            )
        logger.info('{} projects found'.format(len(projects_list)))
        return projects_list

    def show_project(self, project_hashed_id: str):
        url = f'https://api.wistia.com/v1/projects/{project_hashed_id}.json'
        project_details = self.session.get(url).json()
        logger.debug('Retrieved project details: {}'.format(project_details))
        return project_details

    def show_media(self, wistia_hashed_id: str):
        url = f'https://api.wistia.com/v1/medias/{wistia_hashed_id}.json'
        r = self.session.get(url)
        if not r.ok:
            r.raise_for_status()
        media_data = r.json()
        return media_data

    def show_media_customizations(self, wistia_hashed_id: str):
        # https://wistia.com/support/developers/data-api#customizations_show
        url = f'https://api.wistia.com/v1/medias/{wistia_hashed_id}/customizations.json'
        r = self.session.get(url)
        if not r.ok:
            r.raise_for_status()
        media_customizations_data = r.json()
        return media_customizations_data

    def list_captions(self, wistia_hashed_id: str):
        url = f'https://api.wistia.com/v1/medias/{wistia_hashed_id}/captions.json'
        r = self.session.get(url)
        if not r.ok:
            r.raise_for_status()
        caption_list = r.json()
        return caption_list

    def delete_captions(
            self,
            wistia_hashed_id: str,
            language_code: str = 'eng',
    ):
        url = f'https://api.wistia.com/v1/medias/{wistia_hashed_id}/captions/{language_code}.json'
        r = self.session.delete(url)
        if not r.ok:
            r.raise_for_status()

    def enable_captions_for_media(
            self,
            wistia_hashed_id: str,
            enabled: bool = True,
    ) -> dict:
        # https://wistia.com/support/developers/data-api#customizations_update
        url = f'https://api.wistia.com/v1/medias/{wistia_hashed_id}/customizations.json'
        if enabled:
            payload = {'plugin': {'captions-v1': {'onByDefault': False}}}
        else:
            payload = {'plugin': {'captions-v1': None}}
        r = self.session.put(url, json=payload)
        if not r.ok:
            r.raise_for_status()
        media_customizations_data = r.json()
        return media_customizations_data

    def upload_subtitle_file_to_wistia_video(
            self,
            wistia_hashed_id: str,
            subtitle_file_name: str,
            replace=False,
            language_code: str = 'eng',
    ):
        files = {'caption_file': open(subtitle_file_name, 'rb')}

        captions_list = self.list_captions(wistia_hashed_id=wistia_hashed_id)
        replaceable_captions = [
            c for c in captions_list if c['language'] == language_code
        ]

        base_url = 'https://api.wistia.com/v1'
        url_template = '{base_url}/medias/{media_hashed_id}/captions/{language_code}.json'
        if replace and replaceable_captions:
            detail_url = url_template.format(
                base_url=base_url,
                media_hashed_id=wistia_hashed_id,
                language_code=language_code,
            )
            r = self.session.put(detail_url, files=files)
            r.raise_for_status()

        else:
            list_url = f'https://api.wistia.com/v1/medias/{wistia_hashed_id}/captions.json'
            r = self.session.post(
                list_url, data=dict(language_code=language_code), files=files)
            r.raise_for_status()


def find_smallest_video_asset_url(wistia: WistiaClient, wistia_hashed_id: str):
    media_data = wistia.show_media(wistia_hashed_id)
    assets = media_data['assets']
    video_assets = [a for a in assets if a['contentType'] == 'video/mp4']
    smallest_video = sorted(video_assets, key=lambda v: v['fileSize'])[0]
    video_file_url = smallest_video['url'] + '.mp4'  # Append extension
    return video_file_url


@timing
def caption_project(wistia: WistiaClient, project_hashed_id, replace=False):
    project_data = wistia.show_project(project_hashed_id)
    logger.info(
        '"{name}" [{hashedId}] has {mediaCount} media'.format(**project_data))
    logger.info("Gonna captch 'em all!")
    media_list = project_data['medias']

    concurrency = 10
    with terminating(multiprocessing.Pool(processes=concurrency)) as pool:
        results = [
            pool.apply_async(
                subtitle_wistia_video,
                kwds=dict(
                    wistia=wistia,
                    wistia_hashed_id=media_item['hashed_id'],
                    replace=replace,
                ),
            ) for media_item in media_list
        ]
        completed_subtitles = [p.get() for p in results]

    return completed_subtitles


def enable_captions_for_project(
        wistia: WistiaClient,
        project_hashed_id: str,
        enabled: bool = True,
):
    project_data = wistia.show_project(project_hashed_id)
    logger.info(
        '"{name}" [{hashedId}] has {mediaCount} media'.format(**project_data))
    logger.info(f'{"En" if enabled else "Dis"}abling captions...')
    media_list = project_data['medias']

    concurrency = 10
    with terminating(multiprocessing.Pool(processes=concurrency)) as pool:
        results = [
            pool.apply_async(
                wistia.enable_captions_for_media,
                kwds=dict(
                    wistia_hashed_id=media_item['hashed_id'],
                    enabled=enabled,
                ),
            ) for media_item in media_list
        ]
        modified_media_customizations = [p.get() for p in results]

    return modified_media_customizations


def download_file(file_url):
    filename, headers = urllib.request.urlretrieve(file_url)
    return filename


def autosub_video_file(video_file_name, **extra_options):
    srt_file_name = autosub.generate_subtitle_file(
        source_path=video_file_name, **extra_options)
    return srt_file_name


def get_media_url(media_hashed_id: str) -> str:
    return f'https://my.wistia.com/medias/{media_hashed_id}'


def get_project_url(project_hashed_id: str) -> str:
    return f'https://my.wistia.com/projects/{project_hashed_id}'


@timing
def subtitle_wistia_video(wistia: WistiaClient,
                          wistia_hashed_id: str,
                          replace=False,
                          **kwargs,):
    logger.info('Wistia hashed id: {}'.format(wistia_hashed_id))
    video_url = get_media_url(wistia_hashed_id)

    logger.info('Fetching video info')
    # Can raise requests.exceptions.HTTPError (503)
    video_file_url = find_smallest_video_asset_url(wistia, wistia_hashed_id)
    logger.debug('Found smallest video asset url: {}'.format(video_file_url))

    logger.info('Downloading video')
    video_file_name = download_file(video_file_url)
    logger.debug('Downloaded file to {}'.format(video_file_name))

    logger.info('Feeding video to autosub')
    # Can raise google.api_core.exceptions.ResourceExhausted (429)
    subtitle_file_name = autosub_video_file(video_file_name, **kwargs)
    logger.info('Generated subtitle file: {}'.format(subtitle_file_name))

    # Can raise requests.exceptions.HTTPError (503)
    logger.info('Uploading subtitle file to wistia')
    wistia.upload_subtitle_file_to_wistia_video(
        wistia_hashed_id,
        subtitle_file_name,
        replace=replace,
    )

    logger.info('Done!')
    logger.info('Check out the subtitles at: {}'.format(video_url))

    return video_url


def get_client(password: str = ''):
    password = password or environ.get('WISTIA_API_PASSWORD')
    if not password:
        pass
    return WistiaClient(api_password=password)


def main():
    try:
        args = parse_arguments()

        video_hashed_id = args.video
        project_hashed_id = args.project
        list_projects = args.list_projects
        replace = args.replace
        toggle_captions = bool(args.toggle_captions)
        set_captions_to = args.toggle_captions.lower() == 'on'

        wistia = get_client(args.password)

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
                enable_captions_for_project(
                    project_hashed_id, enabled=set_captions_to)
            else:
                caption_project(project_hashed_id, replace=replace)

        elif video_hashed_id:
            if toggle_captions:
                wistia.enable_captions_for_media(
                    video_hashed_id, enabled=set_captions_to)
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
        default='',
        help='Wistia API password',
        action='store',
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
