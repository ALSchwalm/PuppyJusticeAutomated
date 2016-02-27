import math
import json
import os
import urllib.request
from moviepy.editor import *
from random import choice, uniform

""" A mapping of Justices' real names to their 'resource' name
"""
JUSTICE_MAPPING = {
    "John G. Roberts, Jr.": "roberts",
    "Antonin Scalia": "scalia",
    "Ruth Bader Ginsburg": "ginsburg",
    "Sonia Sotomayor": "sotomayor",
    "Elena Kagan": "kagan",
    "Stephen G. Breyer": "breyer",
    "Anthony M. Kennedy": "kennedy",
    "Samuel A. Alito, Jr.": "alito",
    "Clarence Thomas": "thomas"
}

MAX_MISC_TIME = 4
MAX_RELATED_TIME = 7


def random_clip(video, duration):
    assert(duration < video.duration)
    start = uniform(0, video.duration - duration)
    return video.subclip(start, start+duration)


def generate_video_for_speaker(speaker, duration, resources):
    needed_duration = duration
    speaker_resources = resources[speaker]
    misc_resources = resources["misc"]

    clips = []
    while duration > 0:
        c = choice(speaker_resources)
        if c.duration > duration:
            clips.append(random_clip(c, duration))
            duration = 0
        else:
            clips.append(c)
            duration -= c.duration
            m = choice(misc_resources)
            if m.duration > duration:
                if duration > MAX_MISC_TIME:
                    clips.append(random_clip(m, MAX_MISC_TIME))
                    duration -= MAX_MISC_TIME
                else:
                    clips.append(random_clip(m, duration))
                    duration = 0
            else:
                if m.duration > MAX_MISC_TIME:
                    clips.append(random_clip(m, MAX_MISC_TIME))
                    duration -= MAX_MISC_TIME
                else:
                    clips.append(m)
                    duration -= m.duration
    out = concatenate_videoclips(clips)
    assert(math.isclose(out.duration, needed_duration))
    return out


def generate_resource_mapping(base):
    resources_dirs = [d for d in os.listdir(base)
                      if os.path.isdir(os.path.join(base, d))]

    resources = {}
    for resource in resources_dirs:
        video_paths = os.listdir(os.path.join(base, resource))
        clips = [VideoFileClip(os.path.join(base, resource, v))
                 for v in video_paths]
        clips.sort(key=lambda v: v.duration, reverse=True)
        resources[resource] = clips
    return resources


def main():
    resources = generate_resource_mapping("resources")

    url = "https://api.oyez.org/case_media/oral_argument_audio/24097"
    response = urllib.request.urlopen(url)
    data = response.read()
    text = data.decode('utf-8')
    js = json.loads(text)

    subtitle = js["title"]

    transcript = js["transcript"]
    title = transcript["title"]

    print("  {}: \n  {}".format(title, subtitle))

    url = js["media_file"][0]["href"]
    print("Downloading audio from: {}".format(url))

    audio_path = urllib.request.urlretrieve(url)[0]
    audio = VideoFileClip(audio_path)

    sections = transcript["sections"]

    unknown_mapping = {}
    speaker_videos = []
    for i, section in enumerate(sections):
        print("  SECTION: {}".format(i))
        for turn in section["turns"]:
            name = turn["speaker"]["name"]

            if name not in JUSTICE_MAPPING:
                assert(turn["speaker"]["roles"] is None)
                if name not in unknown_mapping.keys():
                    resource = "lawyer" + str(len(unknown_mapping.keys())+1)
                    unknown_mapping[name] = resource
                else:
                    resource = unknown_mapping[name]
            else:
                resource = JUSTICE_MAPPING[name]

            print(name)

            start_time = float(turn["start"])
            end_time = float(turn["stop"])

            if math.isclose(start_time, end_time):
                continue

            print(start_time, end_time)
            assert(end_time > start_time)
            vid = generate_video_for_speaker(resource, end_time - start_time,
                                             resources)
            speaker_videos.append(vid)
            for block in turn["text_blocks"]:
                print("  {}".format(block["text"]))

    out = concatenate_videoclips(speaker_videos)
    out.audio = audio.audio
    out.write_videofile("test.mp4")

if __name__ == "__main__":
    main()
