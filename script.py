import subprocess
import re
import os
import os.path

def bash_command(cmd):
    with open('output.txt', 'w+') as f:
        return subprocess.Popen(cmd, stdout=f, stderr=f)
		
def get_filename_no_ext(filename):
	filename_parts = re.split("\.", filename)[:-1]
	return '.'.join(filename_parts)
	
def verify_success(filename, new_filename):
	if os.path.isfile(new_filename):
		if os.path.getsize(new_filename) > 0:
			with open("successful.txt", "a") as myfile:
				myfile.write(filename + "," + new_filename)
			return
	
	with open("failed.txt", "a") as myfile:
		myfile.write(filename + "," + new_filename)
	os.remove(new_filename)

def parse_codecs(filename):
	bash_command(["./ffmpeg.exe", "-i", filename ]).wait()

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
			
			#codec type is always element 3
			if split_line[2] == 'Video:':
				codec = split_line[3].rstrip("\r\n")
				video_streams.append(codec)

			elif split_line[2] == 'Audio:':
				codec = split_line[3].rstrip("\r\n")
				audio_streams.append(codec)

			elif split_line[2] == 'Subtitle:':
				codec = split_line[3].rstrip("\r\n")
				subtitle_streams.append(codec)
        
	return bitrate, video_streams, audio_streams, subtitle_streams
	

def convert_file(filename, bitrate, video_streams, audio_streams, subtitle_streams):
	
	#making assumption that the only video stream we would care about is the first one.
	source_is_h264 = video_streams[0] == 'h264'
	source_bitrate_ok = bitrate < 8000
	source_all_aac = True
	source_no_subtitles = len(subtitle_streams) == 0
	
	filename_no_ext = get_filename_no_ext(filename)
	new_filename = filename_no_ext + "-new"
	
	for stream in audio_streams:
		if stream != 'aac':
			source_all_aac = False
			
	#the best case, all codecs are good to go; just write a new file
	if source_is_h264 and source_bitrate_ok and source_all_aac :
		new_filename_ext = new_filename + '.mp4'
		print "No codec conversion necessary!"
		print "Writing new file... " + new_filename_ext
		bash_command(["./ffmpeg.exe", "-y", "-i", filename, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-c:a", "copy", new_filename_ext ]).wait()
		
	#just need to convert audio
	elif source_is_h264 and source_bitrate_ok and source_no_subtitles:
		new_filename_ext = new_filename + '.mp4'
		print "Only audio codec conversion required!"
		print "Writing new file... " + new_filename_ext
		bash_command(["./ffmpeg.exe", "-y", "-i", filename, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-c:a", "libfdk_aac", "-q:a", "1", new_filename_ext ]).wait()
		
	# full transcode required
	elif source_no_subtitles:
		new_filename_ext = new_filename + '.mp4'
		print "Full transcode in progress..."
		print "Writing new file... " + new_filename_ext
		bash_command(["./ffmpeg.exe", "-y", "-hwaccel", "cuvid", "-i", filename, "-map", "0:v", "-map", "0:a", "-c:v", "h264_nvenc", "-preset", "slow", "-profile:v", "high", "-b:v", "7M", "-c:a", "libfdk_aac", "-q:a", "1", new_filename_ext ]).wait()		
		
	#codecs fine but subtitles exist so switching to MKV
	elif source_is_h264 and source_bitrate_ok and source_all_aac:
		new_filename_ext = new_filename + '.mkv'
		print "No codec conversion necessary; subtitles found"
		print "Writing new file... " + new_filename_ext
		cmd = bash_command(["./ffmpeg.exe", "-y", "-i", filename, "-map", "0", "-c:v", "copy", "-c:a", "copy", "-c:s", "srt", new_filename_ext ])
		cmd.wait()
		# conversion of subtitles FAILED, just remove them and use MP4
		if cmd.returncode != 0:
			os.remove(new_filename_ext)
			print "Subtitle conversion failed (probably image based).  Removing and retrying as MP4"
			new_filename_ext = new_filename + '.mp4'
			bash_command(["./ffmpeg.exe", "-y", "-i", filename, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-c:a", "copy", new_filename_ext ]).wait()
			
	#subtitles exist and audio codec is wrong
	elif source_is_h264 and source_bitrate_ok:
		new_filename_ext = new_filename + '.mkv'
		print "Only audio codec conversion required; subtitles found"
		print "Writing new file... " + new_filename_ext
		cmd = bash_command(["./ffmpeg.exe", "-y", "-i", filename, "-map", "0", "-c:v", "copy", "-c:a", "libfdk_aac", "-q:a", "1", "-c:s", "srt", new_filename_ext ])
		cmd.wait()
		# conversion of subtitles FAILED, just remove them and use MP4
		if cmd.returncode != 0:
			os.remove(new_filename_ext)
			print "Subtitle conversion failed (probably image based).  Removing and retrying as MP4"				
			new_filename_ext = new_filename + '.mp4'
			bash_command(["./ffmpeg.exe", "-y", "-i", filename, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-c:a", "libfdk_aac", "-q:a", "1", new_filename_ext ]).wait()
		
	#worst case :(.  full transcode with subtitles thrown in
	else:
		new_filename_ext = new_filename + '.mkv'
		print "Full transcode required; subtitles found"
		print "Writing new file... " + new_filename_ext
		cmd = bash_command(["./ffmpeg.exe", "-y", "-hwaccel", "cuvid", "-i", filename, "-map", "0", "-c:v", "h264_nvenc", "-preset", "slow", "-profile:v", "high", "-b:v", "7M", "-c:a", "libfdk_aac", "-q:a", "1", "-c:s", "srt", new_filename_ext])
		cmd.wait()
		# conversion of subtitles FAILED, just remove them and use MP4
		if cmd.returncode != 0:
			os.remove(new_filename_ext)
			print "Subtitle conversion failed (probably image based).  Removing and retrying as MP4"
			new_filename_ext = new_filename + '.mp4'
			bash_command(["./ffmpeg.exe", "-y", "-hwaccel", "cuvid", "-i", filename, "-map", "0:v", "-map", "0:a", "-c:v", "h264_nvenc", "-preset", "slow", "-profile:v", "high", "-b:v", "7M", "-c:a", "libfdk_aac", "-q:a", "1", new_filename_ext]).wait()
			
	verify_success(filename, new_filename_ext)		
		
with open('files_to_convert.txt', 'r') as f:
	content = f.readlines()
	for line in content:
		file_to_convert = line.rstrip("\r\n")
		bitrate, video_streams, audio_streams, subtitle_streams = parse_codecs(file_to_convert)
		convert_file(file_to_convert, bitrate, video_streams, audio_streams, subtitle_streams)
