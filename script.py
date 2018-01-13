import subprocess
import json
import re
import os
import os.path
from pprint import pprint

def bash_command(cmd):
    with open('output.txt', 'w+') as f:
        return subprocess.Popen(cmd, stdout=f, stderr=f)
		
def get_filename_no_ext(filename):
	filename_parts = re.split("\.", filename)[:-1]
	return '.'.join(filename_parts)

def parse_codecs(filename):
	bash_command(["./ffprobe.exe", "-v", "quiet", "-of", "json", "-show_streams", "-show_format", filename]).wait()

	with open('output.txt') as f:
		json_data = json.load(f)
	
	container_streams = []
	
	streams = json_data['streams']
	
	
	for stream in streams:
		stream_struct = {}
		stream_struct['type'] = stream['codec_type']
		stream_struct['codec'] = stream['codec_name']
		stream_struct['language'] = 'und'
		disposition = stream['disposition']
		stream_struct['default'] = disposition['default']
		stream_struct['forced'] = disposition['forced']
		if stream_struct['type'] == 'audio':
			stream_struct['channels'] = stream['channels']
		if 'tags' in stream:
			tags = stream['tags']
			if 'language' in tags:
				stream_struct['language'] = tags['language']
		container_streams.append(stream_struct)
		
	container_structure = {}
	container_structure['streams'] = container_streams
	
	container_structure['bitrate'] = json_data['format']['bit_rate']
	container_structure['length'] = json_data['format']['duration']
	
	return container_structure
	

def convert_file(filename, container_structure):
	
	filename_no_ext = get_filename_no_ext(filename)
	new_filename = filename_no_ext + "-new.mp4"
	
	i = 0
	
	video_stream_index = -1
	audio_stream_index = -1
	
	preamble_args = []
	input_args = []
	map_args = []
	video_args = []
	audio_args = []
	
	input_args.extend(["-i", filename])
	
	#build up video and audio right now only!
	for i in range(len(container_structure['streams'])):
		stream = container_structure['streams'][i]
		if stream['default'] == 0 and stream['forced'] == 0:
			continue
			
		if stream['type'] == 'video' and video_stream_index == -1:
			video_stream_index = i
			
			map_str = "0:" + str(i)
			map_args.extend(["-map", map_str])	
			
			if int(container_structure['bitrate']) > 7500000 or stream['codec'] != 'h264':
				preamble_args.extend(["-hwaccel", "cuvid"])
				video_args.extend(["-c:v:0", "h264_nvenc", "-preset", "slow", "-profile:v", "high", "-b:v", "7M"])
			else:
				video_args.extend(["-c:v:0", "copy"])
				
		
		if stream['type'] == 'audio' and audio_stream_index == -1:
			audio_stream_index = i
			
			map_str = "0:" + str(i)
			
			#leave audio alone if its stereo AAC
			if stream['channels'] <= 2 and stream['codec'] == 'aac':
				map_args.extend(["-map", map_str])			
				audio_args.extend(["-c:a:0", "copy"])
				
			elif stream['channels'] <= 5:
				map_args.extend(["-map", map_str])
				audio_args.extend(["-c:a:0", "aac", "-ac", "2"])
				
			else:
				#ugh we have to make separate files and recombine them later.
				surround_command = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:a:0", "libfdk_aac", "-ac", "6", "6channel.mp4"]
				bash_command(surround_command).wait()
				stereo_command = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:a:0", "libfdk_aac", "-ac", "2", "2channel.mp4"]
				bash_command(stereo_command).wait()
				
				input_args.extend(["-i", "2channel.mp4"])
				input_args.extend(["-i", "6channel.mp4"])
				
				map_args.extend(["-map", "1:0"])
				map_args.extend(["-map", "2:0"])
				
				audio_args.extend(["-c:a:0", "copy"])
				audio_args.extend(["-c:a:1", "copy"])
				
				
	print("Writing new file... " + new_filename)
	
	full_command = ["./ffmpeg.exe", "-y"]
	full_command.extend(preamble_args)
	full_command.extend(input_args)	
	full_command.extend(map_args)
	full_command.extend(video_args)
	full_command.extend(audio_args)
	full_command.append(new_filename)
	print(full_command)
	bash_command(full_command).wait()
	os.remove("2channel.mp4")
	os.remove("6channel.mp4")
	
	#TODO external subtitles...

	
with open('files_to_convert.txt', 'r') as f:
	content = f.readlines()
	for line in content:
		file_to_convert = line.rstrip("\r\n")
		parse_codecs(file_to_convert)
		container_struct = parse_codecs(file_to_convert)
		convert_file(file_to_convert, container_struct)
