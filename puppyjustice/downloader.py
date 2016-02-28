import json
import urllib.request
import logging
from moviepy.editor import *


def download_json(url):
    response = urllib.request.urlopen(url)
    data = response.read()
    text = data.decode('utf-8')
    return json.loads(text)


def download_audio(media_json):
    url = media_json["media_file"][0]["href"]
    logging.info("Downloading audio from: {}".format(url))

    audio_path = urllib.request.urlretrieve(url)[0]
    audio = VideoFileClip(audio_path)
    return audio
