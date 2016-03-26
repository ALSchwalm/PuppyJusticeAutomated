"""
USAGE:
  puppyjustice -h | --help
  puppyjustice --version
  puppyjustice
  puppyjustice <title> <case> <transcript>
"""

import logging
import random
import re
import os
import glob
import json
from docopt import docopt

from puppyjustice import downloader, builder, uploader


def build_video_and_upload_case(title, sub_title, case, description,
                                media_json, resources):
    logging.info("  Downloading audio".format(title))
    audio = downloader.download_audio(media_json)
    if audio is None:
      logging.warning("  Audio download failed. Skipping")
      return

    id = media_json["id"]
    transcript = media_json["transcript"]

    logging.info("  Building subtitles")
    subtitle_location = builder.build_subtitles(transcript, id)

    logging.info("  Building video")
    video = builder.build_video(title, case, resources, transcript, audio)

    logging.info("  Writing video to build/{}.mp4".format(id))
    video.write_videofile("build/{}.mp4".format(id))

    builder.write_random_frame("build/{}.mp4".format(id),
                               5, video.duration - 15,
                               "build/thumbnail.png")

    logging.info("  Uploading video")
    uploader.upload_video("{}: {}".format(title, sub_title),
                          "build/{}.mp4".format(id),
                          subtitle_location,
                          ["puppyjustice", "scotus", "yt:cc=on",
                           "RealAnimalsFakePaws"],
                          description,
                          "build/thumbnail.png")
    logging.info("  Uploading complete")


def was_argued(case):
    for event in case["timeline"]:
        if event["event"] == "Argued":
            return True
    return False


def date_argued(case):
    for event in case["timeline"]:
        if event["event"] == "Argued":
            # TODO I'm not sure what the other dates can be, so just
            # go with the first one
            return event["dates"][0]
    raise ValueError("Request for date of a case that was not argued")


def recent_cases(start_year=2010, end_year=2017, excluding=None):
    urls = []
    for year in range(start_year, end_year):
        url = ("https://api.oyez.org/cases?filter=term:{}".format(year) +
               "&labels=true&page=0&per_page=0")
        urls.append(url)

    json = []
    for url in urls:
        json += downloader.download_json(url)

    cases = [case for case in json if was_argued(case)]
    cases.sort(key=lambda x: date_argued(x))

    for short_case in cases:
        id = short_case["ID"]

        if id in excluding:
            continue
        logging.info("Reading JSON for case {} ({})".format(id, short_case["name"]))

        case_json = downloader.download_json(short_case["href"])
        if case_json["oral_argument_audio"] is None:
            continue

        for i, part in enumerate(case_json["oral_argument_audio"]):
            media_json = downloader.download_json(part["href"])
            oyez_link = short_case["href"].replace("api.oyez.org", "www.oyez.org")
            title = short_case["name"]
            sub_title = part["title"]
            if len(case_json["oral_argument_audio"]) > 1 and "part " not in sub_title.lower():
                sub_title += " (Part {})".format(i+1)

            finished = i == (len(case_json["oral_argument_audio"])-1)
            yield case_json, title, sub_title, media_json, oyez_link, finished


def can_handle_case(case):
    try:
        members = case["heard_by"][0]["members"]
        for member in members:
            if member["name"] not in builder.JUSTICE_MAPPING.keys():
                return False
        return True
    except:
        return False


def sanitize_text(text):
    text = text.replace("</p>", "\n")
    text = text.replace("<br>", "\n")
    text = re.sub("</.*?>", " ", text)
    text = re.sub("<.*?>", "", text)
    return text


if __name__ == "__main__":
    arguments = docopt(__doc__, version='scotus-dogs-automated v0.1')

    # Enable Logging
    logging.basicConfig(filename='puppyjusticeautomated.log',
                        level=logging.DEBUG)

    seed = random.random()
    logging.info("Random seed chosen as: {}".format(seed))

    # For reproducible random choices
    random.seed(seed)

    with open("handled_cases.txt", "r+") as cases_file:
        handled_cases = [int(id) for id in cases_file.readlines()]
    cases_file = open("handled_cases.txt", "a")

    resources = builder.generate_resource_mapping("resources")

    if arguments["<case>"] and arguments["<transcript>"]:
        case = json.load(open(arguments["<case>"]))
        transcript = json.load(open(arguments["<transcript>"]))
        title = arguments["<title>"]

        build_video_and_upload_case(title, case, "description",
                                    transcript, resources)
        exit(0)


    for case, title, sub_title, media_json, oyez_link, finished in recent_cases(
            excluding=handled_cases):
        if not can_handle_case(case) or media_json["transcript"] is None:
            cases_file.write(str(case["ID"]) + "\n")
            logging.info("Skipping case {}".format(case["ID"]))
            continue

        description = "Facts:\n"
        description += sanitize_text(case["facts_of_the_case"])

        description += "Question:\n"
        question = sanitize_text(case["question"])
        description += question

        if case["conclusion"] and len(description) + len(case["conclusion"]) < 4000:
            description += "Conclusion:\n"
            description += sanitize_text(case["conclusion"])

        description += "\nFor more information about this case see: {}\n\n".format(
            oyez_link)

        for i, section in enumerate(media_json["transcript"]["sections"]):
            start_time = float(section["start"]) * 1000
            time = builder.milli_to_timecode(start_time, short=True)

            description += "Section {}: {}\n".format(i+1, time)

        description += ("\n\nPuppyJusticeAutomated videos are created by a program "
                        "written by Adam Schwalm. This program is available on "
                        "github here: https://github.com/ALSchwalm/PuppyJusticeAutomated\n\n")

        description += (
            "The audio and transcript used in this video is provided "
            "by the Chicago-Kent College of Law under the terms of the "
            "Creative Commons Attribution-NonCommercial 4.0 International License. "
            "See this link for details: https://creativecommons.org/licenses/by-nc/4.0/"
        )

        # Max youtube description length
        assert(len(description) < 5000)

        build_video_and_upload_case(title, sub_title, case, description,
                                    media_json, resources)

        if finished:
            cases_file.write(str(case["ID"]) + "\n")

        for f in glob.glob('build/*'):
            os.remove(f)
