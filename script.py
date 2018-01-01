import subprocess
import re

def bash_command(cmd):
    with open('output.txt', 'w+') as f:
        return subprocess.Popen(cmd, stdout=f, stderr=f)


bash_command(["./ffmpeg.exe", "-i", "rev_out.mkv" ]).wait()

with open('output.txt') as f:
    content = f.readlines()

video_streams = []
audio_streams = []
subtitle_streams = []

for line in content:
    if line.startswith("  Duration"):
        line = line[2:]
        split_line = re.split(" ", line)

        #bitrate is element 5
        bitrate = int(split_line[5])

    if line.startswith("    Stream #0"):
        line = line[4:]
        split_line = re.split(" ", line)
        
        if split_line[2] == 'Video:':
            codec = split_line[3].rstrip("\r\n")
            video_streams.append(codec)

        elif split_line[2] == 'Audio:':
            codec = split_line[3].rstrip("\r\n")
            audio_streams.append(codec)

        elif split_line[2] == 'Subtitle:':
            codec = split_line[3].rstrip("\r\n")
            subtitle_streams.append(codec)
        
print bitrate
print video_streams
print audio_streams
print subtitle_streams

