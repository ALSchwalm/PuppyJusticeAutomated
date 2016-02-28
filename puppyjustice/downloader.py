import json
import urllib.request
import logging
from moviepy.editor import *


def download_json(url):
    response = urllib.request.urlopen(url)
    data = response.read()
    text = data.decode('utf-8')
    return json.loads(text)

#js = download_json("https://api.oyez.org/case_media/oral_argument_audio/24097")
# resources = generate_resource_mapping("resources")
# video = build_video(resources, transcript, audio)
# video.write_videofile("{}.mp4".format(title))

def download_audio(media_json):
    url = media_json["media_file"][0]["href"]
    logging.info("Downloading audio from: {}".format(url))

    audio_path = urllib.request.urlretrieve(url)[0]
    audio = VideoFileClip(audio_path)
    return audio
