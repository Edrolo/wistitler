from pathlib import Path
from requests import JSONDecodeError

from typing import (
    List,
    Tuple,
)

from dataclasses import dataclass

import json

import functools
import logging
import nlpcloud
import os
import pysrt
from time import sleep

from helpers import cache_as_json


logger = logging.getLogger(__name__)

token = os.getenv("NLPCLOUD_KEY")


@functools.lru_cache()
def get_async_client():
    return nlpcloud.Client("whisper", token, gpu=True, asynchronous=True)


def experiment():

    file1 = "http://embed.wistia.com/deliveries/a56af8d0d02031eb3656618573ce1c682ed51461.bin"
    file2 = "http://embed.wistia.com/deliveries/d1816ac81b17a3cdcf69859219f8ed20dd271e53.bin"
    file_demo = "https://ia801405.us.archive.org/17/items/children_at_play_2210.poem_librivox/childrenatplay_davies_ah_64kb.mp3"

    # client = get_async_client()
    # response_data = client.asr(url=file1)
    # result_url = response_data["url"]
    # result_data = {}
    #
    # while not result_data:
    #     print("Waiting 10 seconds")
    #     sleep(10)
    #     result_data = client.async_result(result_url)

    srt_file_name, srt_file  = generate_subtitles_for_video_at_url(url=file2, key="file2")

    example_result_data = {
        "created_on": "2022-11-18T15:56:16.536025Z",
        "request_body": '{"url":"https://ia801405.us.archive.org/17/items/children_at_play_2210.poem_librivox/childrenatplay_davies_ah_64kb.mp3"}',
        "finished_on": "2022-11-18T15:56:29.393898Z",
        "http_code": 200,
        "error_detail": "",
        "content": '{"text":" CHILDREN AT PLAY by William Henry Davies Read for LibriVox.org by Anita Hibbard, September 27, 2022 I hear a merry noise indeed. Is it the geese and ducks that take their first plunge in a quiet pond, that into scores of ripples break? Or children make this merry sound. I see an oak tree, its strong back could not be bent an inch, though all its leaves were stone, or iron even. A boy, with many a lusty call, rides on a bough bareback through heaven. I see two children dig a hole, and plant in it a cherry stone. We\'ll come tomorrow, one child said, and then the tree will be full grown and all its boughs have cherries red. Ah, children, what a life to lead! You love the flowers, but when they\'re past, no flowers are missed by your bright eyes, and when cold winter comes at last, snowflakes shall be your butterflies.","duration":82,"language":"en","segments":[{"id":0,"seek":0,"start":0.0,"end":8.94,"text":" CHILDREN AT PLAY by William Henry Davies Read for LibriVox.org by Anita Hibbard, September"},{"id":1,"seek":0,"start":8.94,"end":11.76,"text":" 27, 2022"},{"id":2,"seek":0,"start":11.76,"end":14.8,"text":" I hear a merry noise indeed."},{"id":3,"seek":0,"start":14.8,"end":21.04,"text":" Is it the geese and ducks that take their first plunge in a quiet pond, that into scores"},{"id":4,"seek":0,"start":21.04,"end":22.96,"text":" of ripples break?"},{"id":5,"seek":0,"start":22.96,"end":26.04,"text":" Or children make this merry sound."},{"id":6,"seek":2604,"start":26.04,"end":32.64,"text":" I see an oak tree, its strong back could not be bent an inch, though all its leaves were"},{"id":7,"seek":2604,"start":32.64,"end":35.04,"text":" stone, or iron even."},{"id":8,"seek":2604,"start":35.04,"end":41.84,"text":" A boy, with many a lusty call, rides on a bough bareback through heaven."},{"id":9,"seek":2604,"start":41.84,"end":46.8,"text":" I see two children dig a hole, and plant in it a cherry stone."},{"id":10,"seek":2604,"start":46.8,"end":53.68,"text":" We\'ll come tomorrow, one child said, and then the tree will be full grown and all its boughs"},{"id":11,"seek":2604,"start":53.68,"end":56.0,"text":" have cherries red."},{"id":12,"seek":5600,"start":56.0,"end":59.76,"text":" Ah, children, what a life to lead!"},{"id":13,"seek":5600,"start":59.76,"end":66.24,"text":" You love the flowers, but when they\'re past, no flowers are missed by your bright eyes,"},{"id":14,"seek":6624,"start":66.24,"end":91.56,"text":" and when cold winter comes at last, snowflakes shall be your butterflies."}]}',
    }

    print(srt_file_name, srt_file.text)


result = {
    "created_on": "2023-01-13T21:14:48.282656Z",
    "request_body": '{"url":"http://embed.wistia.com/deliveries/a56af8d0d02031eb3656618573ce1c682ed51461.bin","encoded_file":null,"input_language":null}',
    "finished_on": "2023-01-13T21:14:52.726425Z",
    "http_code": 200,
    "error_detail": "",
    "content": '{"text":" So if we look at what the response is, it is social health and well-being, because we know that whenever there is a conflict with your parents or conflict with anyone, that would affect our social health and our social well-being.","duration":21,"language":"en","segments":[{"id":0,"seek":0,"start":0.0,"end":5.8,"text":" So if we look at what the response is, it is social health and well-being, because we"},{"id":1,"seek":0,"start":5.8,"end":11.48,"text":" know that whenever there is a conflict with your parents or conflict with anyone, that"},{"id":2,"seek":1148,"start":11.48,"end":30.2,"text":" would affect our social health and our social well-being."}]}',
}
content = {
    "text": " So if we look at what the response is, it is social health and well-being, because we know that whenever there is a conflict with your parents or conflict with anyone, that would affect our social health and our social well-being.",
    "duration": 21,
    "language": "en",
    "segments": [
        {
            "id": 0,
            "seek": 0,
            "start": 0.0,
            "end": 5.8,
            "text": " So if we look at what the response is, it is social health and well-being, because we",
        },
        {
            "id": 1,
            "seek": 0,
            "start": 5.8,
            "end": 11.48,
            "text": " know that whenever there is a conflict with your parents or conflict with anyone, that",
        },
        {
            "id": 2,
            "seek": 1148,
            "start": 11.48,
            "end": 30.2,
            "text": " would affect our social health and our social well-being.",
        },
    ],
}


@cache_as_json(filename_pattern="request_async_asr__{key}.json")
def request_async_asr(*, url, nlp_client, key):
    return nlp_client.asr(url=url)


@cache_as_json(filename_pattern="retrieve_async_asr_result__{key}.json")
def retrieve_async_asr_result(*, url, nlp_client, key):
    try:
        return nlp_client.async_result(url=url)
    except JSONDecodeError as e:
        print(e)
        raise


def async_asr_for_url(*, url, nlp_client, key):
    response_data = request_async_asr(url=url, nlp_client=nlp_client, key=key)
    retrieval_url = response_data["url"]
    result_data = retrieve_async_asr_result(
        url=retrieval_url, nlp_client=nlp_client, key=key
    )

    while not result_data:
        print(f"{url}: Waiting 10 seconds")
        sleep(10)
        result_data = retrieve_async_asr_result(
            url=retrieval_url, nlp_client=nlp_client, key=key
        )

    return result_data


@dataclass
class SubtitleLine:
    start_ms: int
    end_ms: int
    text: str


def generate_subtitles_for_video_at_url(*, url, key, **kwargs) -> Tuple[str, pysrt.SubRipFile]:
    nlp_client = get_async_client()
    subtitle_data = async_asr_for_url(url=url, nlp_client=nlp_client, key=key)
    content = json.loads(subtitle_data["content"])
    """
        "id": 2,
        "seek": 1148,
        "start": 11.48,
        "end": 30.2,
        "text": " would affect our social health and our social well-being.",
    """

    srt_file = srt_file_from_nlp_asr_result(content)

    filename = save_srt_file(srt_file=srt_file, key=key)
    return filename, srt_file


def save_srt_file(*, srt_file: pysrt.SubRipFile, key: str):
    srt_folder = Path("./srt/")
    srt_folder.mkdir(exist_ok=True)
    filename = srt_folder / f"{key}.srt"
    srt_file.save(filename)
    return filename


def srt_file_from_nlp_asr_result(content):
    subtitle_lines = [
        SubtitleLine(
            start_ms=int(segment["start"] * 1000),
            end_ms=int(segment["end"] * 1000),
            text=segment["text"],
        )
        for segment in content["segments"]
    ]
    return srt_formatter(subtitle_lines, show_before_ms=300, show_after_ms=300)


def srt_formatter(
    subtitles: List[SubtitleLine],
    show_before_ms: int = 0,
    show_after_ms: int = 0,
):
    """Taken from autosub.formatters"""
    sub_rip_file = pysrt.SubRipFile()
    srt_items = [
        pysrt.SubRipItem(
            index=i,
            text=subtitle_line.text,
            start=max(0, subtitle_line.start_ms - show_before_ms),
            end=subtitle_line.end_ms + show_after_ms,
        )
        for i, subtitle_line in enumerate(subtitles, start=1)
    ]
    sub_rip_file.extend(srt_items)
    # return "\n".join(str(item) for item in sub_rip_file)
    return sub_rip_file


if __name__ == "__main__":
    experiment()
