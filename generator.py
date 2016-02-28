import math
import json
import os
import urllib.request
import random
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
MIN_CLIP_DURATION = 1.8


def random_clip(video, duration):
    assert(duration < video.duration)
    start = uniform(0, video.duration - duration)
    return video.subclip(start, start+duration)


def generate_video_for_speaker(speaker, duration, resources):
    needed_duration = duration
    speaker_resources = resources[speaker]
    misc_resources = resources["misc"]

    clips = []
    while duration > MIN_CLIP_DURATION:
        c = choice(speaker_resources)
        if c.duration > duration:
            clips.append(random_clip(c, duration))
            duration = 0
        else:
            clips.append(c)
            duration -= c.duration
            m = choice(misc_resources)
            if m.duration > duration:

                # There must be a little time after the cut but before the end
                # of this turn.
                if duration > MAX_MISC_TIME + MIN_CLIP_DURATION:
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
    if len(clips) > 0:
        out = concatenate_videoclips(clips)
        return out
    else:
        return None


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


def is_short(turn):
    duration = turn_duration(turn)
    if duration < 2:
        return True
    return False


def turn_duration(turn):
    start_time = float(turn["start"])
    end_time = float(turn["stop"])
    return end_time - start_time


def build_video(resources, transcript, audio):
    sections = transcript["sections"]

    underflow_duration = 0
    unknown_mapping = {}
    speaker_videos = []
    for section in sections:
        turns = section["turns"]
        turn_num = 0
        while turn_num < len(turns):
            turn = turns[turn_num]
            name = turn["speaker"]["name"]

            if name not in JUSTICE_MAPPING:
                assert(turn["speaker"]["roles"] is None)
                if name not in unknown_mapping.keys():
                    n = len(unknown_mapping.keys()) % 2
                    resource = "lawyer" + str(n)
                    unknown_mapping[name] = resource
                else:
                    resource = unknown_mapping[name]
            else:
                resource = JUSTICE_MAPPING[name]

            print(name)

            duration = turn_duration(turn)
            if duration < 0.001:
                turn_num += 1
                continue

            # Detect the pattern where a speaker is briefly interrupted
            if turn_num + 2 < len(turns):
                next_turn = turns[turn_num + 1]
                next_next_turn = turns[turn_num + 2]
                if is_short(next_turn) and next_next_turn["speaker"]["name"] == name:
                    duration += turn_duration(next_turn)
                    duration += turn_duration(next_next_turn)
                    turn_num += 2

            vid = generate_video_for_speaker(resource,
                                             duration + underflow_duration,
                                             resources)
            if vid is None:
                underflow_duration += duration
                turn_num += 1
                continue

            speaker_videos.append(vid)
            if not math.isclose(duration + underflow_duration, vid.duration):
                underflow_duration += duration - vid.duration
            else:
                underflow_duration = 0

            for block in turn["text_blocks"]:
                print("  {}".format(block["text"]))
            turn_num += 1

    out = concatenate_videoclips(speaker_videos)
    out.audio = audio.audio
    return out


def main():
    # For reproducible random choices
    random.seed(1)
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

    video = build_video(resources, transcript, audio)

    print(video.duration, audio.duration)
    video.write_videofile("test.mp4")

if __name__ == "__main__":
    main()
