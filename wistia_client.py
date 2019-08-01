from os import environ

import requests

import logging
logger = logging.getLogger(__name__)


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
        r.raise_for_status()
        media_data = r.json()
        return media_data

    def show_media_customizations(self, wistia_hashed_id: str):
        # https://wistia.com/support/developers/data-api#customizations_show
        url = f'https://api.wistia.com/v1/medias/{wistia_hashed_id}/customizations.json'
        r = self.session.get(url)
        r.raise_for_status()
        media_customizations_data = r.json()
        return media_customizations_data

    def list_captions(self, wistia_hashed_id: str):
        url = f'https://api.wistia.com/v1/medias/{wistia_hashed_id}/captions.json'
        r = self.session.get(url)
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
        r.raise_for_status()

    def order_captions(self, wistia_hashed_id: str):
        url_from_docs = 'https://api.wistia.com/v1/medias/{media_hashed_id}/captions/purchase.json'
        url_from_UI = 'https://{account-slug}.wistia.com/medias/{media_hashed_id}/transcript.json'

        base_url = 'https://api.wistia.com/v1'
        url = f'{base_url}/medias/{wistia_hashed_id}/captions/purchase.json'

        r = self.session.post(url)
        r.raise_for_status()
        return r

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


def get_client(password: str = ''):
    password = password or environ.get('WISTIA_API_PASSWORD')
    if not password:
        pass
    return WistiaClient(api_password=password)
