""" USAGE: puppyjustice.py

puppyjustice.py -h | --help
puppyjustice.py --version
"""

import logging
import random
import re
from docopt import docopt

from puppyjustice import downloader, builder, uploader


def build_video_and_upload_case(title, description, media_json, resources):
    logging.info("  Downloading audio".format(title))
    audio = downloader.download_audio(media_json)
    transcript = media_json["transcript"]

    logging.info("  Building subtitles")
    subtitle_location = builder.build_subtitles(transcript)

    logging.info("  Building video")
    video = builder.build_video(resources, transcript, audio)

    logging.info("  Writing video to {}.mp4".format(title))
    video.write_videofile("{}.mp4".format(title))

    logging.info("  Uploading video")
    uploader.upload_video(title,
                          "{}.mp4".format(title),
                          subtitle_location,
                          ["puppyjustice", "scotus"],
                          description)
    logging.info("  Uploading complete")


def cases_during_year(year, excluding):
    url = ("https://api.oyez.org/cases?filter=term:{}".format(year) +
           "&labels=true&page=0&per_page=0")

    logging.info("Downloading cases from: {}".format(url))

    json = downloader.download_json(url)
    for short_case in json:
        id = short_case["ID"]

        if id in excluding:
            continue
        logging.info("Reading JSON for case {} ({})".format(id, short_case["name"]))

        case_json = downloader.download_json(short_case["href"])
        media_json = downloader.download_json(
            case_json["oral_argument_audio"][0]["href"])
        yield case_json, short_case["name"], media_json


def can_handle_case(case):
    members = case["heard_by"][0]["members"]
    for member in members:
        if member["name"] not in builder.JUSTICE_MAPPING.keys():
            return False
    return True


def sanitize_text(text):
    text = text.replace("</p>", "\n")
    text = text.replace("<br>", "\n")
    text = re.sub("</.*?>", " ", text)
    text = re.sub("<.*?>", "", text)
    return text


if __name__ == "__main__":
    arguments = docopt(__doc__, version='scotus-dogs-automated v0.1')

    # Enable Logging
    logging.basicConfig(filename='scotus-dogs-automated.log',
                        level=logging.DEBUG)

    seed = random.random()
    logging.info("Random seed chosen as: {}".format(seed))

    # For reproducible random choices
    random.seed(seed)

    with open("handled_cases.txt", "w+") as cases_file:
        handled_cases = [int(id) for id in cases_file.readlines()]

    resources = builder.generate_resource_mapping("resources")

    for case, title, media_json in cases_during_year(
            2010, excluding=handled_cases):
        if not can_handle_case(case):
            logging.info("Skipping case {}".format(case["ID"]))
            continue

        description = "Question:\n"
        description += sanitize_text(case["question"])

        description += "Facts:\n"
        description += sanitize_text(case["facts_of_the_case"])

        if case["conclusion"]:
            description += "Conclusion:\n"
            description += sanitize_text(case["conclusion"])

        build_video_and_upload_case(title, description, media_json, resources)
        handled_cases.write(str(case["ID"]) + "\n")
