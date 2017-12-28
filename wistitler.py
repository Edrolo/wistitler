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
from subprocess import check_output
from time import time
from six.moves import urllib

import requests

module = sys.modules['__main__'].__file__
logger = logging.getLogger(module)

WISTIA_API_PASSWORD = environ.get('WISTIA_API_PASSWORD')

session = requests.Session()
session.auth = ('api', WISTIA_API_PASSWORD)


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
        logger.info(
            'func:%r args:[%r, %r] took: %2.4f sec' %
            (f.__name__, args, kwargs, end_time - start_time)
        )
        return result

    return wrap


def list_all_projects(s=session):
    logger.info('Listing all projects')
    projects_url = 'https://api.wistia.com/v1/projects.json'
    projects_list = []
    for page in range(1, 21):
        next_page_response = s.get('{}?page={}'.format(projects_url, page))
        next_page_response.raise_for_status()
        next_page_of_projects = next_page_response.json()
        if next_page_of_projects:
            projects_list += next_page_of_projects
        else:
            break
    else:
        logger.warning('More than 2000 Wistia projects! Might need to increase limits in code')
    logger.info('{} projects found'.format(len(projects_list)))
    return projects_list


def show_project(project_hashed_id, s=session):
    url = 'https://api.wistia.com/v1/projects/{hashed_id}.json'.format(
        hashed_id=project_hashed_id,
    )
    project_details = s.get(url).json()
    logger.debug('Retrieved project details: {}'.format(project_details))
    return project_details


@timing
def caption_project(project_hashed_id, replace=False, s=session):
    project_data = show_project(project_hashed_id)
    logger.info('"{name}" [{hashedId}] has {mediaCount} media'.format(**project_data))
    logger.info("Gonna captch 'em all!")
    media_list = project_data['medias']

    concurrency = 10
    with terminating(multiprocessing.Pool(processes=concurrency)) as pool:
        results = [
            pool.apply_async(
                subtitle_wistia_video,
                kwds=dict(
                    wistia_hashed_id=media_item['hashed_id'],
                    replace=replace,
                    s=s,
                ),
            )
            for media_item in media_list
        ]
        completed_subtitles = [p.get() for p in results]

    return completed_subtitles


def find_smallest_video_asset_url(wistia_hashed_id, s=session):
    media_data = show_media(wistia_hashed_id, s=s)
    assets = media_data['assets']
    video_assets = [a for a in assets if a['contentType'] == 'video/mp4']
    smallest_video = sorted(video_assets, key=lambda v: v['fileSize'])[0]
    video_file_url = smallest_video['url'] + '.mp4'  # Append extension
    return video_file_url


def show_media(wistia_hashed_id, s=session):
    url = 'https://api.wistia.com/v1/medias/{media_hashed_id}.json'.format(
        media_hashed_id=wistia_hashed_id,
    )
    r = s.get(url)
    if not r.ok:
        r.raise_for_status()
    media_data = r.json()
    return media_data


def download_file(file_url):
    filename, headers = urllib.request.urlretrieve(file_url)
    return filename


def autosub_video_file(video_file_name):
    command = ['autosub', video_file_name]
    output = check_output(command)
    last_line = output.splitlines()[-1].decode()
    prefix = 'Subtitles file created at '
    if last_line.startswith(prefix):
        srt_file_name = last_line[len(prefix):]
        return srt_file_name
    else:
        raise RuntimeError('Strange output from autosub: "{}"'.format(output))


def upload_subtitle_file_to_wistia_video(
    wistia_hashed_id,
    subtitle_file_name,
    replace=False,
    s=session,
):
    language_code = 'eng'
    files = {'caption_file': open(subtitle_file_name, 'rb')}

    list_url = 'https://api.wistia.com/v1/medias/{media_hashed_id}/captions.json'.format(
        media_hashed_id=wistia_hashed_id,
    )
    r = s.get(list_url)
    r.raise_for_status()

    captions_list = r.json()
    replaceable_captions = [c for c in captions_list if c['language'] == language_code]

    base_url = 'https://api.wistia.com/v1'
    url_template = '{base_url}/medias/{media_hashed_id}/captions/{language_code}.json'
    if replace and replaceable_captions:
        detail_url = url_template.format(
            base_url=base_url,
            media_hashed_id=wistia_hashed_id,
            language_code=language_code,
        )
        r = s.put(detail_url, files=files)
        r.raise_for_status()

    else:
        r = s.post(list_url, data=dict(language_code=language_code), files=files)
        r.raise_for_status()


@timing
def subtitle_wistia_video(wistia_hashed_id, replace=False, s=session):
    logger.info('Wistia hashed id: {}'.format(wistia_hashed_id))
    video_url = 'https://my.wistia.com/medias/{wistia_hashed_id}'.format(
        wistia_hashed_id=wistia_hashed_id,
    )

    logger.info('Fetching video info')
    video_file_url = find_smallest_video_asset_url(wistia_hashed_id, s=s)
    logger.debug('Found smallest video asset url: {}'.format(video_file_url))

    logger.info('Downloading video')
    video_file_name = download_file(video_file_url)
    logger.debug('Downloaded file to {}'.format(video_file_name))

    logger.info('Feeding video to autosub')
    subtitle_file_name = autosub_video_file(video_file_name)
    logger.info('Generated subtitle file: {}'.format(subtitle_file_name))

    logger.info('Uploading subtitle file to wistia')
    upload_subtitle_file_to_wistia_video(
        wistia_hashed_id,
        subtitle_file_name,
        replace=replace,
        s=s,
    )

    logger.info('Done!')
    logger.info('Check out the subtitles at: {}'.format(video_url))

    return video_url


def main():
    try:
        args = parse_arguments()

        video_hashed_id = args.video
        project_hashed_id = args.project
        list_projects = args.list_projects
        replace = args.replace

        logging.basicConfig(
            level=args.loglevel,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )

        if list_projects:
            projects = sorted(list_all_projects(), key=lambda p: p['name'])
            for index, project in enumerate(projects):
                print('{}. {hashedId}: {name}'.format(index, **project))

        elif project_hashed_id:
            caption_project(project_hashed_id, replace=replace)

        elif video_hashed_id:
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
        ),
    )
    parser.add_argument(
        '-d', '--debug',
        help='Print lots of debugging statements',
        action='store_const', dest='loglevel', const=logging.DEBUG,
        default=logging.WARN,
    )
    parser.add_argument(
        '--verbose',
        help='Be verbose',
        action='store_const', dest='loglevel', const=logging.INFO,
    )
    parser.add_argument(
        '-r', '--replace',
        help='Replace existing captions if present',
        action='store_true',
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-v', '--video',
        help='Hashed ID of video to caption',
    )
    group.add_argument(
        '-p', '--project',
        help='Caption all videos in project with given hashed_id',
    )
    group.add_argument(
        '-l', '--list-projects',
        help='Print a list of all projects in your Wistia account',
        action='store_true',
    )
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    sys.exit(main())
