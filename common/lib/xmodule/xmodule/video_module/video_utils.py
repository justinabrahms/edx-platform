"""
Module containts utils specific for video_module but not for transcripts.
"""
import json
import logging
import urllib
import requests
import re
from urlparse import urlparse

from django.conf import settings
from requests.exceptions import RequestException
from boto.s3.connection import S3Connection

log = logging.getLogger(__name__)


def create_youtube_string(module):
    """
    Create a string of Youtube IDs from `module`'s metadata
    attributes. Only writes a speed if an ID is present in the
    module.  Necessary for backwards compatibility with XML-based
    courses.
    """
    youtube_ids = [
        module.youtube_id_0_75,
        module.youtube_id_1_0,
        module.youtube_id_1_25,
        module.youtube_id_1_5
    ]
    youtube_speeds = ['0.75', '1.00', '1.25', '1.50']
    return ','.join([
        ':'.join(pair)
        for pair
        in zip(youtube_speeds, youtube_ids)
        if pair[1]
    ])


def get_video_from_cdn(cdn_base_url, original_video_url):
    """
    Get video URL from CDN.

    `original_video_url` is the existing video url.
    Currently `cdn_base_url` equals 'http://api.xuetangx.com/edx/video?s3_url='
    Example of CDN outcome:
        {
            "sources":
                [
                    "http://cm12.c110.play.bokecc.com/flvs/ca/QxcVl/u39EQbA0Ra-20.mp4",
                    "http://bm1.42.play.bokecc.com/flvs/ca/QxcVl/u39EQbA0Ra-20.mp4"
                ],
            "s3_url": "http://s3.amazonaws.com/BESTech/CS169/download/CS169_v13_w5l2s3.mp4"
        }
    where `s3_url` is requested original video url and `sources` is the list of
    alternative links.
    """

    if not cdn_base_url:
        return None

    request_url = cdn_base_url + urllib.quote(original_video_url)

    try:
        cdn_response = requests.get(request_url, timeout=0.5)
    except RequestException as err:
        log.info("Request timed out to CDN server: %s", request_url, exc_info=True)
        return None

    if cdn_response.status_code == 200:
        cdn_content = json.loads(cdn_response.content)
        return cdn_content['sources'][0]
    else:
        return None


def get_s3_transient_url(video_url, expires_in=10):
    """
    Get S3 transient video url.
    """
    if (not getattr(settings, 'VIDEO_LINK_TRANSIENCE', {}).get("AWS_ACCESS_KEY") or
            not getattr(settings, 'VIDEO_LINK_TRANSIENCE', {}).get("AWS_SECRET_KEY")):
        log.info("Video Link Transience Credentials are not present")
        return None

    conn = S3Connection(
        settings.VIDEO_LINK_TRANSIENCE["AWS_ACCESS_KEY"],
        settings.VIDEO_LINK_TRANSIENCE["AWS_SECRET_KEY"]
    )

    # Get bucket and video name from video_url.
    # Valid patterns for constructing S3 URLs:
    # http(s)://<bucket>.s3.amazonaws.com/<object>
    # http(s)://s3.amazonaws.com/<bucket>/<object>
    # http(s)://s3-region.amazonaws.com/<bucket>/<object>

    for pattern in [r':\/\/s3(?:.*).amazonaws.com\/(?P<bucket_name>[^\/]+)\/(?P<video_name>.+)',
                    r':\/\/(?P<bucket_name>.+).s3(?:.*).amazonaws.com\/(?P<video_name>.+)']:
        names = re.compile(pattern)
        result = names.search(video_url)
        if result:
            bucket_name, video_name = result.groups()[0], result.groups()[1]
            return conn.generate_url(expires_in, 'GET', bucket_name, video_name)

    return None
