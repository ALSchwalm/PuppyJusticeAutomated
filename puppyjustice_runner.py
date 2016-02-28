""" USAGE: puppyjustice.py

puppyjustice.py -h | --help
puppyjustice.py --version
"""

import logging
import random
from docopt import docopt

from puppyjustice import downloader, builder, uploader

if __name__ == "__main__":
    arguments = docopt(__doc__, version='scotus-dogs-automated v0.1')

    # For reproducible random choices
    random.seed(1)

    # Enable Logging
    logging.basicConfig(filename='scotus-dogs-automated.log',
                        level=logging.DEBUG)

    media_json = downloader.download_json(
        "https://api.oyez.org/case_media/oral_argument_audio/24097")

    audio = downloader.download_audio(media_json)
    transcript = media_json["transcript"]

    subtitle_location = builder.build_subtitles(transcript)
    resources = builder.generate_resource_mapping("resources")

    title = transcript["title"]

    video = builder.build_video(resources, transcript, audio)
    video.write_videofile("{}.mp4".format(title))

    uploader.upload_video(title, "{}.mp4".format(title),
                          ["puppyjustice", "scotus"],
                          "temp description")
