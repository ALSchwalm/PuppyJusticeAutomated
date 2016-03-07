import os
import math
import subprocess
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
RECENT_SPEAKER_THRESHOLD = 6
MAX_CHARACTERS_PER_SUBTITLE = 85
INTRO_DURATION = 6
CROSSFADE_DURATION = 1
MIN_SPEAKER_INTRO_DURATION = 3


def milli_to_timecode(ms, short=False):
    # Timecode must take into account the intro, but minus the crossfade
    ms += (INTRO_DURATION - CROSSFADE_DURATION) * 1000

    milli = int(ms % 1000)
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000*60)) % 60)
    hours = int((ms / (1000*60*60)) % 24)

    if short is False:
        return "{0:02d}:{1:02d}:{2:02d}.{3:03d}".format(
            hours, minutes, seconds, milli)
    else:
        return "{0:02d}:{1:02d}:{2:02d}".format(
            hours, minutes, seconds)


def write_timecode(start_ms, end_ms, file):
    start = milli_to_timecode(start_ms)
    end = milli_to_timecode(end_ms)
    file.write("{},{}\n".format(start, end))


def block_parts(text, start, end):
    duration = end - start
    words = text.split()
    sub_text = ""

    prior_time = start
    for word in words:
        sub_text += " " + word
        if len(sub_text) + len(word) >= MAX_CHARACTERS_PER_SUBTITLE:
            sub_end = prior_time + duration*len(sub_text)/len(text)
            yield sub_text.strip(), prior_time, sub_end
            prior_time = sub_end
            sub_text = ""
    yield sub_text.strip(), prior_time, end


def write_subtitle_file(transcript, destination):
    sections = transcript["sections"]
    with open(destination, "w", encoding='utf-8') as file:
        for section in sections:
            for turn in section["turns"]:
                for block_num, block in enumerate(turn["text_blocks"]):
                    start_time = float(block["start"]) * 1000
                    end_time = float(block["stop"]) * 1000
                    block_text = block["text"]

                    if turn["speaker"] and block_num == 0:
                        sub_name = turn["speaker"]["last_name"].split()[-1]
                        block_text = sub_name + ": " + block_text

                    for sub, sub_start, sub_end in block_parts(block_text,
                                                               start_time,
                                                               end_time):
                        if sub == "":
                            continue
                        write_timecode(sub_start,
                                       sub_end,
                                       file)
                        file.write(sub + "\n")
                        file.write("\n")


def random_clip(video, duration):
    assert(duration < video.duration)
    start = uniform(0, video.duration - duration)
    clip = video.subclip(start, start+duration)
    assert(math.isclose(clip.duration, duration))
    return clip


def get_speaker_info_by_id(case, speaker_id):
    for advocate in case["advocates"]:
        if advocate["advocate"]["ID"] == speaker_id:
            return (advocate["advocate"]["name"],
                    advocate["advocate_description"])

    for court in case["heard_by"]:
        for justice in court["members"]:
            if justice["ID"] == speaker_id:
                return (justice["name"],
                        justice["roles"][0]["role_title"])
    assert(False)


def generate_speaker_intro(speaker_id, case, video):
    name, description = get_speaker_info_by_id(case, speaker_id)

    intro_settings = {
        "color": 'white',
        "method": "label",
    }

    intro_text = TextClip(name, fontsize=40,
                          font="Bookman-URW-Demi-Bold",
                          stroke_color="black",
                          stroke_width=2,
                          **intro_settings)

    background = ImageClip('resources/speaker_background.png')

    intro_text = intro_text.set_pos((80, 550))
    background = background.set_pos((60, 540))

    layers = [video,
              background,
              intro_text]

    if description:
        subtitle_text = TextClip(description, fontsize=20,
                                 font="Bookman-URW-Light-Italic",
                                 **intro_settings)
        subtitle_text = subtitle_text.set_pos((80, 600))
        layers.append(subtitle_text)

    intro = CompositeVideoClip(layers, size=(1280, 720))
    intro = intro.set_duration(video.duration)
    return intro


def generate_video_for_speaker(resource_id, duration, resources,
                               no_skip=False, introduction=False,
                               case=None, speaker_id=None):
    orig_duration = duration
    misc_resources = resources["misc"]
    speaker_resources = resources[resource_id]

    if duration < 0:
        return None, duration

    clips = []
    while duration > MIN_CLIP_DURATION or no_skip:
        no_skip = False

        # We have not yet created an introduction
        if introduction is True and len(clips) == 0:
            video = speaker_resources[0]  # just take the longest one
            c = generate_speaker_intro(speaker_id, case, video)
        else:
            c = choice(speaker_resources)

        if c.duration > duration:
            if introduction is True and duration < MIN_SPEAKER_INTRO_DURATION:
                clips.append(random_clip(c, MIN_SPEAKER_INTRO_DURATION))
                duration -= MIN_SPEAKER_INTRO_DURATION
            else:
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
        out = concatenate(clips)
        assert(math.isclose(out.duration + duration, orig_duration))
        return out, duration
    else:
        return None, None


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


def has_spoken_recently(prior_turns, speaker):
    # TODO this does not account for speakers who were skipped
    recent_turns = prior_turns[-RECENT_SPEAKER_THRESHOLD:]
    recent_speakers = [turn_speaker(t) for t in recent_turns]
    return speaker in recent_speakers


def is_short(turn):
    duration = turn_duration(turn)
    if duration < MIN_CLIP_DURATION:
        return True
    return False


def turn_duration(turn):
    start_time = float(turn["start"])
    end_time = float(turn["stop"])
    return end_time - start_time


def same_speaker(turn, speaker):
    return turn_speaker(turn) == speaker


def turn_speaker(turn):
    if turn["speaker"]:
        return turn["speaker"]["name"]
    else:
        return None


def write_random_frame(vid_path, start, end, path):
    time = uniform(start, end)
    subprocess.call(["ffmpeg",
                     "-y",
                     "-ss", str(time),
                     "-i", vid_path,
                     "-vframes", "1",
                     path])


def generate_intro(title):
    assert(title.count(" v. ") == 1)
    title = title.replace(" v. ", "\nv.\n")

    title_settings = {
        "color": 'white',
        "stroke_color": "black",
        "stroke_width": 2,
        "method": "caption",
        "size": (900, None),
        "font": 'Bookman-URW-Demi-Bold',
    }

    title_txt = TextClip(title, fontsize=65, **title_settings)
    background = ImageClip('resources/intro_background.png')

    intro = CompositeVideoClip([
        background,
        title_txt.set_pos(('center', 'center')),
    ], size=(1280, 720))

    intro.end = INTRO_DURATION
    intro.duration = INTRO_DURATION
    return intro


def build_video(title, case, resources, transcript, audio):
    sections = transcript["sections"]

    current_remainder = 0
    unknown_mapping = {}
    has_been_introduced = []
    speaker_videos = []
    for section in sections:
        turns = section["turns"]
        turn_num = 0
        while turn_num < len(turns):
            turn = turns[turn_num]
            name = turn_speaker(turn)

            if name is None:
                remainder += turn_duration(turn)
                turn_num += 1
                continue

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

            speaker_id = turn["speaker"]["ID"]
            duration = turn_duration(turn)

            # Just skip very short turns
            if duration < 0.001:
                turn_num += 1
                continue

            if len(turns) > turn_num+2 and \
                    is_short(turns[turn_num+1]) and \
                    has_spoken_recently(turns[:turn_num+1],
                                        turn_speaker(turns[turn_num+1])) and \
                    same_speaker(turns[turn_num+2], name):
                duration += turn_duration(turns[turn_num+1])
                duration += turn_duration(turns[turn_num+2])
                turn_num += 2

            if duration > 2 and speaker_id not in has_been_introduced:
                vid, remainder = generate_video_for_speaker(resource,
                                                            duration + current_remainder,
                                                            resources,
                                                            no_skip=True,
                                                            introduction=True,
                                                            case=case,
                                                            speaker_id=speaker_id)
                has_been_introduced.append(speaker_id)
            else:
                vid, remainder = generate_video_for_speaker(resource,
                                                            duration + current_remainder,
                                                            resources,
                                                            no_skip=True)

            # The duration we got plus the remainder should be equal
            # to the duration we requested
            assert(math.isclose(vid.duration + remainder,
                                duration + current_remainder))

            if vid is None and remainder is None:
                current_remainder = duration
                turn_num += 1
                continue
            elif vid is None:
                current_remainder = remainder
            else:
                current_remainder = remainder
                speaker_videos.append(vid)
            turn_num += 1

    intro = generate_intro(title)
    first, *speaker_videos = speaker_videos

    intro_and_first = CompositeVideoClip([
        intro,
        first.set_start(intro.end-CROSSFADE_DURATION).crossfadein(
            CROSSFADE_DURATION)])
    intro_and_first = intro_and_first.set_duration(
        intro.duration + first.duration - CROSSFADE_DURATION)

    ending = VideoFileClip("resources/disclaimer.mp4")
    out = concatenate([intro_and_first] + speaker_videos + [ending],
                      method="compose")
    out.audio = audio.audio
    out.audio.start = intro.duration - CROSSFADE_DURATION
    return out


def build_subtitles(transcript):
    title = transcript["title"]
    write_subtitle_file(transcript, "build/{}.txt".format(title))
    return "build/{}.txt".format(title)
