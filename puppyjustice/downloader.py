import json
import urllib.request
import logging
import gzip
from io import BytesIO
from moviepy.editor import *


def download_json(url):
    print("Downloading URL: {}".format(url))

    request = urllib.request.Request(url)
    request.add_header('Accept-encoding', 'gzip')
    response = urllib.request.urlopen(request)
    if response.info().get('Content-Encoding') == 'gzip':
      buf = BytesIO(response.read())
      f = gzip.GzipFile(fileobj=buf)
      data = f.read()
    else:
      data = response.read()
    text = data.decode('utf-8')
    return json.loads(text)


def download_audio(media_json):
   for media in media_json["media_file"]:
     try:
       url = media["href"]
       logging.info("Downloading audio from: {}".format(url))

       audio_path = urllib.request.urlretrieve(url)[0]
       audio = VideoFileClip(audio_path)
       return audio
     except:
       continue
