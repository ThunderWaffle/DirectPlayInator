import subprocess
import json
import re
import os
import ntpath
from pprint import pprint
import sys
import shutil

def bash_command(cmd, filename='output.txt'):
	with open(filename, 'w+') as f:
		return subprocess.Popen(cmd, stdout=f, stderr=f)

'''
def unix_to_win_filename(filename):
	parts = []
	remaining_name = os.path.abspath(filename)
	while True:
		new_parts = os.path.split(remaining_name)
		if new_parts[0] == remaining_name:
			parts.insert(0, new_parts[0])
			break
		else:
			remaining_name = new_parts[0]
			parts.insert(0, new_parts[1])

	parts = parts[2:] #cut /mnt
	parts[0] = parts[0] + ':\\'

	return ntpath.join(*parts)
'''

def parse_codecs(filename):
	#win_filename = unix_to_win_filename(filename)
	bash_command(["./ffprobe.exe", "-v", "quiet", "-of", "json", "-show_streams", "-show_format", filename]).wait()

	with open('output.txt') as f:
		try:
			json_data = json.load(f)
		except:
			return False
	
	container_streams = []
	
	if 'streams' not in json_data:
		return False
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
	
def check_results(old_file_structure, desired_streams, new_filename):
	
	if not os.path.isfile(new_filename):
		return False
	
	new_file_structure = parse_codecs(new_filename)
	if new_file_structure == False:
		return False
	
	video_streams = 0
	audio_streams = 0
	
	streams = new_file_structure['streams']
	pprint(streams)
	for stream in streams:
		if stream['type'] == 'video':
			video_streams += 1
		elif stream['type'] == 'audio':
			audio_streams += 1

	if (video_streams + audio_streams) != desired_streams:
		return False

	old_duration = float(old_file_structure['length'])
	new_duration = float(new_file_structure['length'])
	
	if abs(old_duration - new_duration) > 5:
		return False
		
	return True
	
	
	
def convert_av(filename, container_structure):
	
	filename_no_ext, file_ext = os.path.splitext(filename)
	new_filename = filename_no_ext + "-new.mp4"
	
	try:
		os.remove(new_filename)
	except:
		pass
	
	#win_filename = unix_to_win_filename(filename)
	#new_win_filename = unix_to_win_filename(new_filename)
	
	i = 0
	
	video_stream_index = -1
	audio_stream_index = -1
	
	input_args = []
	map_args = []
	
	waits = []
	
	for i in range(len(container_structure['streams'])):
		stream = container_structure['streams'][i]
		if stream['default'] == 0 and stream['forced'] == 0:
			continue
			
		if stream['type'] == 'video' and video_stream_index == -1:
			video_stream_index = i
			
			map_str = "0:" + str(i)
			video_command = []
			
			if int(container_structure['bitrate']) > 7500000 or stream['codec'] != 'h264':
				video_command = ["./ffmpeg.exe", "-y", "-hwaccel", "cuvid", "-i", filename]
				video_command.extend(["-map", map_str])
				video_command.extend(["-c:v:0", "h264_nvenc", "-preset", "slow", "-profile:v", "high", "-b:v", "7M"])
			else:
				video_command = ["./ffmpeg.exe", "-y", "-i", filename]
				video_command.extend(["-map", map_str])
				video_command.extend(["-c:v:0", "copy"])
				
			video_command.extend(["video.mp4"])
			waits.append(bash_command(video_command, 'video_output.txt'))
			
			input_args.extend(["-i", "video.mp4"])
			map_args.extend(["-map", "0:0"])
			
		
		if stream['type'] == 'audio' and audio_stream_index == -1:
			audio_stream_index = i
			
			map_str = "0:" + str(i)
			
			input_args.extend(["-i", "2channel.mp4"])
			map_args.extend(["-map", "1:0"])
			
			#leave audio alone if its stereo AAC
			if stream['channels'] <= 2 and stream['codec'] == 'aac':
				stereo_command = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:a:0", "copy", "2channel.mp4"]
				waits.append(bash_command(stereo_command, '2channel_output.txt'))
				
			elif stream['channels'] <= 5:
				stereo_command = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:a:0", "libfdk_aac", "-ac", "2", "2channel.mp4"]
				waits.append(bash_command(stereo_command, '2channel_output.txt'))
				
			else:
				surround_command = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:a:0", "libfdk_aac", "-ac", "6", "6channel.mp4"]
				waits.append(bash_command(surround_command, '6channel_output.txt'))
				stereo_command = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:a:0", "libfdk_aac", "-ac", "2", "2channel.mp4"]
				waits.append(bash_command(stereo_command, '2channel_output.txt'))
				
				#add 6 channel track
				input_args.extend(["-i", "6channel.mp4"])
				map_args.extend(["-map", "2:0"])
				
	print("Writing new file... " + new_filename)
	
	for active_process in waits:
		active_process.wait()
	
	if audio_stream_index > -1 and video_stream_index > -1:
		full_command = ["./ffmpeg.exe", "-y"]
		full_command.extend(input_args)	
		full_command.extend(map_args)
		full_command.extend(["-codec", "copy"])	
		full_command.append("final-video.mp4")
		print(full_command)
		bash_command(full_command).wait()
	
	print("Conversion Complete!... " + new_filename)
	shutil.copy("final-video.mp4", new_filename)
	
	try:
		os.remove("video.mp4")	
		os.remove("final-video.mp4")
		os.remove("2channel.mp4")
		os.remove("6channel.mp4")
	except:
		pass
		
	return check_results(container_structure, len(input_args) // 2, new_filename)
		
		
def convert_subtitles(filename, container_structure):
	
	#win_filename = unix_to_win_filename(filename)
	filename_no_ext, file_ext = os.path.splitext(filename)
	
	non_forced_index = -1
	non_forced_und_index = -1
	forced_index = -1
	forced_und_index = -1
	
	for i in range(len(container_structure['streams'])):
		stream = container_structure['streams'][i]
		
		if stream['type'] == 'subtitle':
			if stream['language'] == 'en' or stream['language'] == 'eng':
				if stream['forced'] == 1 and forced_index == -1:
					forced_index = i
				elif non_forced_index == -1:
					non_forced_index = i
					
			elif stream['language'] == 'und':
				if stream['forced'] == 1 and forced_und_index == -1:
					forced_und_index = i
				elif non_forced_und_index == -1:
					non_forced_und_index = i
			
	if non_forced_index != -1:
		map_str = "s:0:" + str(non_forced_index)
		new_filename = filename_no_ext + '.eng.srt'
		#new_win_filename = unix_to_win_filename(new_filename)
		command_line = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:s:0", "srt", new_filename]
		if bash_command(command_line).wait() != 0:
			try:
				os.remove(new_filename)
			except:
				pass
		
	if forced_index != -1:
		map_str = "s:0:" + str(forced_index)
		new_filename = filename_no_ext + '.eng.forced.srt'
		#new_win_filename = unix_to_win_filename(new_filename)
		command_line = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:s:0", "srt", new_filename]
		if bash_command(command_line).wait() != 0:
			try:
				os.remove(new_filename)
			except:
				pass
		
	if non_forced_und_index != -1:
		map_str = "s:0:" + str(non_forced_und_index)
		new_filename = filename_no_ext + '.und.srt'
		#new_win_filename = unix_to_win_filename(new_filename)
		command_line = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:s:0", "srt", new_filename]
		if bash_command(command_line).wait() != 0:
			try:
				os.remove(new_filename)
			except:
				pass
		
	if forced_und_index != -1:
		map_str = "s:0:" + str(forced_und_index)
		new_filename = filename_no_ext + '.und.forced.srt'
		#new_win_filename = unix_to_win_filename(new_filename)
		command_line = ["./ffmpeg.exe", "-y", "-i", filename, "-map", map_str, "-c:s:0", "srt", new_filename]
		if bash_command(command_line).wait() != 0:
			try:
				os.remove(new_filename)
			except:
				pass
			
def mark_success(filename):
	with open('successful.txt', 'a') as f:
		f.write(filename)
		
def mark_failure(filename):
	with open('failed.txt', 'a') as f:
		f.write(filename)
		
if len(sys.argv) >= 2:
	with open('files_to_convert.txt', 'w') as f:
		for root, dirs, files in os.walk(os.path.abspath(sys.argv[1])):
				for file in files:
					print(str(os.path.join(root, file)) + '\n')
					f.write(str(os.path.join(root, file)) + '\n')
		
with open('files_to_convert.txt', 'r') as f:
	content = f.readlines()
	for line in content:
		file_to_convert = line.rstrip("\r\n")
		container_struct = parse_codecs(file_to_convert)

		if container_struct == False:
			mark_failure(file_to_convert)
			continue
		
		if convert_av(file_to_convert, container_struct) == False:
			mark_failure(file_to_convert)
			continue
			
		convert_subtitles(file_to_convert, container_struct)
		mark_success(file_to_convert)
