import os
import sys
import re
import subprocess
import datetime
import shutil
import hashlib

# screw this old lexer
import kv_lexer as lexer


# how the awful crc checking works:
# it makes a crc for every time range, input video name, output video name, verbose, and final encode
# and dumps it all to a file if it doesn't exist
# it scans that file to see if any crc matches what we have

# TODO: add hash checking for dates and stuff


def FindItemInList(search_list, item, return_value=False):
    if item in search_list:
        if return_value:
            return search_list[search_list.index(item) + 1]
        else:
            return True
    else:
        return False


def FindCommand( arg, short_arg ):
    found = FindItemInList(sys.argv, arg, False)
    if not found:
        found = FindItemInList(sys.argv, short_arg, False)
    return found


def FindCommandValue( arg, short_arg ):
    value = FindItemInList(sys.argv, arg, True)
    if not value:
        value = FindItemInList(sys.argv, short_arg, True)
    return value


# ok, what the fuck am i doing with all these paths?
class VideoFile:
    def __init__(self, filename, root_folder, config_folder, output_folder, force_file_ext):

        self.output_folder = output_folder

        self.raw_path = os.path.normpath(filename)
        self.path = os.path.normpath(output_folder + os.sep + filename)
        
        if force_file_ext:
            prefix = os.path.splitext(self.path)[0]
            if "." not in force_file_ext:
                force_file_ext = "." + force_file_ext
            self.path = os.path.normpath( prefix + force_file_ext )

        if os.sep in self.path:
            self.filename = self.path.rsplit( os.sep, 1 )[1]
        else:
            self.filename = self.path

        if os.path.isabs( output_folder ):
            self.full_path = self.path
        else:
            self.full_path = os.path.normpath( config_folder + self.path )

        self.full_output_path = self.full_path.rsplit( os.sep, 1 )[0] + os.sep

        self.root_config_folder = config_folder
        self.root_video_folder = root_folder
        self.input_videos = []
        self.time = None

        self.global_ffmpeg_cmd = []
        self.global_filter_complex = []

        self.skip = False  # this will be set to true if the crc check fails
        self.crc_list = []
        
        # dumb temp thing that will be here for 40 years
        self.use_filter_complex_default = True

    def AddInputVideo(self, input_video_filename, check=True):

        if os.path.isabs( input_video_filename ):
            full_input_video_path = input_video_filename
        else:
            full_input_video_path = os.path.normpath(self.root_video_folder + input_video_filename)

        if check:
            for input_video_obj in self.input_videos:
                if full_input_video_path == input_video_obj.abspath:
                    return

        input_video = InputVideoFile( input_video_filename, self.root_video_folder, self.root_config_folder )
        input_video.ffmpeg_cmd_line.extend(self.global_ffmpeg_cmd)
        input_video.filter_complex_list.extend(self.global_filter_complex)
        self.input_videos.append( input_video )

    def AddTimeRange(self, start, end):
        # maybe i should use a filename and get the index instead? idk
        input_video = self.input_videos[-1]
        input_video.AddTimeRange(start, end)
    
    def AddFFMpegCommand(self,ffmpeg_cmd):
        ffmpeg_cmd = ffmpeg_cmd.replace("'", "\"")
        self.input_videos[-1].ffmpeg_cmd_line.append(ffmpeg_cmd)

    def AddFFMpegFilterComplex(self,filter_complex_option):
        self.input_videos[-1].filter_complex_list.append(filter_complex_option)


class InputVideoFile:
    def __init__(self, filename, root_folder, config_folder):
        if os.path.isabs(filename):
            self.abspath = os.path.normpath( filename )
        else:
            self.abspath = os.path.normpath( root_folder + filename )

        self.filename = os.path.basename(self.abspath)

        # bad idea?
        if os.path.isabs(filename):
            self.raw_path = os.path.normpath(filename)
        else:
            append_folder = ''.join( root_folder.split( config_folder, 1 ) )
            self.raw_path = os.path.normpath(append_folder + filename)

        self.time_ranges = []
        self.ffmpeg_cmd_line = []
        self.filter_complex_list = []

    def AddTimeRange(self, start, end):
        self.time_ranges.append([ConvertTimestampToTimeDelta(start), ConvertTimestampToTimeDelta(end)])

    def GetTimeRange(self, list_index):
        dt_start = self.time_ranges[list_index][0]
        dt_end = self.time_ranges[list_index][1]
        dt_diff = GetTimeDiff(dt_start, dt_end)
        return dt_start, dt_end, dt_diff

    def AddFFMpegCommand(self,ffmpeg_cmd):
        ffmpeg_cmd = ffmpeg_cmd.replace("'", "\"")
        self.ffmpeg_cmd_line.append(ffmpeg_cmd)

    def AddFFMpegFilterComplex(self,filter_complex_option):
        self.filter_complex_list.append(filter_complex_option)
        
        
def GetTimeDiff(dt_start, dt_end):
    time_difference = dt_end.total_seconds() - dt_start.total_seconds()
    if time_difference <= 0:
        raise Exception("Time difference less than 0: " + str(time_difference))
    return datetime.timedelta(seconds=time_difference)


def ConvertTimestampToTimeDelta(timestamp_str):
    time_split = timestamp_str.split(":")
    time_split.reverse()
    
    total_seconds = float(time_split[0])
    
    for index in range(1, len(time_split)):
        total_seconds += int(time_split[index]) * (60 ** index)
    
    time_dt = datetime.timedelta(seconds=total_seconds)
    
    return time_dt


def ConvertToDateTime(datetime_str):
    date, time = datetime_str.split(" ", 1)
    year, month, day = date.split('-')
    hour, minute, second = time.split('-')
    
    date_time = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
    
    return date_time


def CreateDirectory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def RemoveDirectory(directory):
    if os.path.isdir(directory):
        shutil.rmtree(directory)


def DeleteFile( path ):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def ParseConfig( config_blocks, base_output_folder, config_folder ):
    if verbose:
        print( "Parsing Config" )

    full_root_folder = config_folder
    full_output_folder = base_output_folder
    force_file_ext = False
    time_stamp = None

    video_list = []
    for block_obj in config_blocks:

        if block_obj.key == "$base_output_folder" or block_obj.key == "$output_folder":
            base_output_folder = os.path.normpath( block_obj.value ) + os.sep
            full_output_folder = base_output_folder

        elif block_obj.key == "$append_output_folder":
            if os.path.isabs( block_obj.value ):
                full_output_folder = os.path.normpath( block_obj.value )
            else:
                full_output_folder = os.path.normpath( base_output_folder + block_obj.value )

        elif block_obj.key == "$force_file_ext":
            force_file_ext = block_obj.value

        elif block_obj.key == "$include":
            include_config = lexer.ReadFile(block_obj.value)
            config_path = os.path.join(full_root_folder, os.path.split(block_obj.value)[0])

            include_video_list, base_output_folder = ParseConfig(include_config, base_output_folder, config_path)

            video_list.extend(include_video_list)

        elif block_obj.key in {"$input_video_folder", "$input_folder"}:
            if os.path.isabs( block_obj.value ):
                full_root_folder = os.path.normpath( block_obj.value ) + os.sep
            else:
                full_root_folder = os.path.normpath( config_folder + block_obj.value ) + os.sep

        # is a video file
        else:

            video_file = VideoFile( block_obj.key, full_root_folder, config_folder,
                                    full_output_folder, force_file_ext )

            if block_obj.items:
                AddInputVideosToVideo( video_file, block_obj )

            video_list.append(video_file)

            video_file.crc_list.append(GetCRC(base_output_folder))
            video_file.crc_list.append(GetCRC(str(final_encode)))

            if not os.path.isfile(video_file.full_path):
                continue

            elif not CheckCRC(video_file, video_file.crc_list):
                video_file.skip = True

    return video_list, base_output_folder


def AddInputVideosToVideo( video_file, block_obj ):
    for input_video_block in block_obj.items:

        crc_list = []
        input_video_block.key = os.path.normpath( input_video_block.key )

        if input_video_block.key == "$time":
            # TODO: maybe if the value is 'self', use the input video date modified?
            #  you might not be able to get a date modified due to no input videos being added, oof
            #  and what if there is more than one video?
            time_stamp = ConvertToDateTime(input_video_block.value)
            video_file.time = time_stamp

        elif input_video_block.key == "$ffmpeg_cmd":
            video_file.global_ffmpeg_cmd.append(input_video_block.value)
            crc_list.append(GetCRC(input_video_block.value))

        elif input_video_block.key == "$no_filter_complex_default":
            video_file.use_filter_complex_default = False

        elif input_video_block.key == "$filter_complex":
            video_file.global_filter_complex.append(input_video_block.value)
            crc_list.append(GetCRC(input_video_block.value))

        elif ":" in input_video_block.key and not os.sep in input_video_block.key:
            video_file.AddInputVideo( video_file.raw_path )
            crc_list.append( GetCRC(video_file.raw_path) )
            crc_list = AddInputVideoSetting( video_file, input_video_block, crc_list )

        else:
            video_file.AddInputVideo(input_video_block.key, False)
            for in_video_item in input_video_block.items:
                crc_list = AddInputVideoSetting( video_file, in_video_item, crc_list )

        video_file.crc_list.extend( crc_list )
    return


def AddInputVideoSetting( video_file, in_video_item, crc_list ):
    if in_video_item.key == "$ffmpeg_cmd":
        video_file.AddFFMpegCommand(in_video_item.value)
        crc_list.append(GetCRC(in_video_item.value))
    
    elif in_video_item.key == "$filter_complex":
        video_file.AddFFMpegFilterComplex(in_video_item.value)
        crc_list.append(GetCRC(in_video_item.value))
    
    else:
        video_file.AddTimeRange(in_video_item.key, in_video_item.value)
        
        crc_list.append(GetCRC(in_video_item.key))
        crc_list.append(GetCRC(in_video_item.value))
            
    return crc_list


# some shitty thing to print what we just parsed
def PrintTimestampsFile( video_list, out_folder ):
    cmd_bar_line = "-----------------------------------------------------------"

    print( cmd_bar_line )

    if verbose:
        print( "Timestamps File" )
        print( cmd_bar_line )
        for out_video in video_list:
            print( out_video.path )

            for in_video in out_video.input_videos:
                print( "    " + in_video.raw_path )

                for time_range in in_video.time_ranges:
                    print( "        " + str(time_range[0]) + " - " + str(time_range[1]) )

            print( "" )
    print( "Default Output Folder: " + out_folder )
    if final_encode:
        print( "Final Encode - Using H265 - CRF 8 - Slow Preset" )
    else:
        print( "Quick Encode - Using H264 - CRF 24 - Ultrafast Preset" )
    print( cmd_bar_line )

    return


def RunFFMpegConCat(temp_path, sub_video_list, out_video):
    # stuff for ffmpeg concat shit
    temp_file = temp_path + "temp.txt"
    with open(temp_file, "w", encoding="utf-8") as temp_file_io:
        for sub_video in sub_video_list:
            temp_file_io.write("file '" + sub_video + "'\n")

    metadata = []
    if out_video.time:
        metadata.append('-metadata date="' + str(out_video.time).replace(':', '-') + '"')

    ffmpeg_command = (
        ffmpeg_bin + "ffmpeg -y -hide_banner",
        "-safe 0 -f concat -i \"" + temp_file + '"',
        "-c copy -map 0",
        *metadata,
        '"' + out_video.full_path + '"'
    )

    RunFFMpeg(out_video.full_path, ' '.join(ffmpeg_command))

    if verbose:
        print("Created Output Video")
    
    if out_video.time:
        ReplaceDateModified(out_video.full_path, out_video.time.timestamp())
        if verbose:
            print("Changed Date Modified")
    
    os.remove(temp_file)


def RunFFMpegSubVideo( time_range_number, input_video, temp_video, use_filter_complex_default ):

    dt_start, dt_end, dt_diff = input_video.GetTimeRange( time_range_number )
    time_start = str(dt_start)
    time_end = str(dt_end)
    time_diff = str(dt_diff)
    
    video_len = GetVideoLength(input_video.abspath)
    
    if video_len < dt_start:
        raise Exception( "start time bad" )

    ffmpeg_command = [
        ffmpeg_bin + "ffmpeg",
        "-y -hide_banner",
        "-ss " + time_start,
        '-i "' + input_video.abspath + '"',
        "-map 0:v"
    ]

    # get audio track count
    audio_tracks = GetAudioTrackCount(input_video.abspath)

    if final_encode:
        ffmpeg_command.append("-c:v libx265")
        ffmpeg_command.append("-crf 8")
        ffmpeg_command.append("-preset slow")
    else:
        ffmpeg_command.append("-c:v libx264")
        ffmpeg_command.append("-crf 24")
        ffmpeg_command.append("-preset ultrafast")

    # TODO: make sure the output colors are not messed up with this

    # shadowplay color range: Limited
    # shadowplay color primaries: BT.601 NTSC
    # shadowplay color space: YUV
    # shadowplay standard: PAL

    # what does this do?
    # "-h full"

    # this stretches the color range i think, so it looks like fucking shit with limited color range
    # ffmpeg_command.append("-vf scale=in_range=limited:out_range=full")

    # ffmpeg_command.append("-vf colormatrix bt709")

    # Filter complex stuff here:
    filter_complex = []

    # this is really just a hardcoded hack since this is what i use it for lmao
    if use_filter_complex_default:
        if audio_tracks == 5 or audio_tracks == 4:
            filter_complex.append("[0:a:1][0:a:2]amerge[audio_combine]")
        elif audio_tracks == 2:
            filter_complex.append("[0:a:0][0:a:1]amerge[audio_combine]")
        else:
            ffmpeg_command.append("-map 0:a")
    else:
        ffmpeg_command.append("-map 0:a")
        
    filter_complex += input_video.filter_complex_list

    if filter_complex:
        ffmpeg_command.append( '-filter_complex "' + ';'.join(filter_complex) + '"' )
        
        if use_filter_complex_default and (audio_tracks == 5 or audio_tracks == 4 or audio_tracks == 2):
            ffmpeg_command.append( "-map \"[audio_combine]\"" )
        
    # TODO: maybe move these hard coded colorspace things to maybe a color command in the config?
    #  $colors "full" / "limited"
    if audio_tracks == 5:
        ffmpeg_command.append("-pix_fmt yuvj420p")
        
    elif audio_tracks == 4 or audio_tracks == 2:
        # Shadowplay - PAL - bad colors:
        ffmpeg_command.append("-colorspace bt470bg -color_primaries bt470bg -color_trc gamma28")

    # NTSC - OBS?:
    # ffmpeg_command.append("-colorspace smpte170m -color_primaries smpte170m -color_trc smpte170m")

    # TODO: test this on newer clips with full color range
    # i do notice very minor color changes with this from limited to full
    # doesn't do anything?
    # ffmpeg_command.append("-pix_fmt yuvj420p")
    # ffmpeg_command.append("-pix_fmt yuv420p")

    ffmpeg_command.append("-c:a libvorbis")
    # This is a bug in ffmpeg, so im using libvorbis for now until this is fixed
    # ffmpeg_command.append("-c:a libopus")

    ffmpeg_command.append("-b:a 192k")

    ffmpeg_command.append("-t " + time_diff)

    # any custom commands
    ffmpeg_command.extend( input_video.ffmpeg_cmd_line )

    # output file
    ffmpeg_command.append('"' + temp_video + '"')

    total_frames = GetTotalFrameCount( dt_diff, GetFrameRate(input_video.abspath) )

    if verbose:
        print("Start: " + time_start + " - End: " + time_end)
        print("Total Frames: " + str(total_frames))

    RunFFMpeg(temp_video, ' '.join(ffmpeg_command), total_frames)

    return


def GetFrameRate( video_path ):
    command = (
        ffmpeg_bin + "ffprobe",
        "-v 0",
        "-of csv=p=0",
        "-select_streams v:0",
        "-show_entries stream=r_frame_rate",
        '"' + video_path + '"'
    )

    output = subprocess.check_output(' '.join(command), shell=True)

    output = str(output).replace("\\r", "").replace("\\n", "").replace("\'", "")[1:]
    numerator, denominator = output.split( "/" )
    frame_rate = int(numerator) / int(denominator)

    return frame_rate


def GetTotalFrameCount( dt_time_length, frame_rate ):
    return dt_time_length.total_seconds() * frame_rate


def RunFFMpeg( out_file, cmd, total_frames=None ):

    if raw_ffmpeg:
        subprocess.run( cmd )
        if not os.path.isfile(out_file) or os.path.getsize(out_file) == 0:
            raise Exception("ffmpeg died")
    else:
        ffmpeg_run = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        if total_frames:
            UpdateProgressBar( 0.00, 52 )  # start it at 0

        ffmpeg_output = ''
        for line in ffmpeg_run.stdout:
            ffmpeg_output += line
            if total_frames:
                if "frame=" in line:
                    # use the total time range and divide it by ffmpeg's current time in the encode to get a percentage
                    current_frame = line.split("frame= ")[1].split(" fps=")[0]
                    percentage = GetPercent( int(current_frame),  total_frames, 2 )
                    UpdateProgressBar( percentage, 52 )
                    # TODO: IDEA: replace the progress bar with "\n" once it's done?

        if total_frames:
            UpdateProgressBar(100.0, 52)  # usually it finishes before we can catch the last frame
            
        if not os.path.isfile(out_file) or os.path.getsize(out_file) == 0:
            print()
            raise Exception("ffmpeg died - output:\n\n" + ffmpeg_output)


def GetPercent( current_frame, total_frames, round_num ):
    return round(( current_frame / total_frames ) * 100, round_num)


def UpdateProgressBar( percentage, width ):
    block = int(round(width * (percentage / 100)))
    text = "\r{0} {1}%".format( "█" * block + "░"*( width - block ), percentage )
    sys.stdout.write( text )
    sys.stdout.flush()


def GetAudioTrackCount( video ):
    ffprobe_command = (
        ffmpeg_bin + "ffprobe",
        "-loglevel error",
        "-show_entries stream=codec_type",
        "-of csv=p=0",
        '"' + video + '"',
    )

    output = subprocess.check_output( ' '.join( ffprobe_command ), shell=True )

    # now clean up that output and shove it into a list
    stream_list = str( output ).split( "\\n" )

    audio_tracks = 0
    for stream in stream_list:
        if "audio" in stream:
            audio_tracks += 1

    return audio_tracks


def GetVideoLength(video):
    ffprobe_command = ffmpeg_bin + \
                      "ffprobe -threads 6 -v error -show_entries format=duration " \
                      "-of default=noprint_wrappers=1:nokey=1 \"" + video + '"'
    
    output = subprocess.check_output(ffprobe_command, shell=True)
    
    # clean up the output
    str_video_length = str(output).split("\\n")[0].split("\\r")[0].split("b\'")[1]
    
    if str_video_length == "N/A":
        return None
    
    return ConvertTimestampToTimeDelta(str_video_length)


def StartEncodingVideos( video_list ):
    temp_folder = "TEMP" + os.sep + str(datetime.datetime.now()) + os.sep
    temp_folder = temp_folder.replace(":", "-").replace(".", "-")
    temp_path = root_folder + temp_folder
    CreateDirectory(temp_path)

    for output_video in video_list:
        if output_video.skip:
            continue
            
        print(output_video.path)

        temp_video_list = []
        temp_video_num = 0
        for input_video in output_video.input_videos:

            print("\nInput: " + input_video.filename)

            time_range_number = 0
            while time_range_number < len(input_video.time_ranges):

                temp_video = temp_path + str(temp_video_num) + ".mkv"
                temp_video_list.append( temp_video )

                RunFFMpegSubVideo(time_range_number, input_video, temp_video, output_video.use_filter_complex_default)
                
                time_range_number += 1
                temp_video_num += 1

                if time_range_number < len(input_video.time_ranges):
                    print()
            print()

        CreateDirectory( output_video.full_output_path )

        # now combine all the sub videos together
        RunFFMpegConCat(temp_path, temp_video_list, output_video)
        print()

        MakeCRCFile(output_video.filename, output_video.crc_list)

        print("-----------------------------------------------------------")

    RemoveDirectory(temp_path)  # TODO: has an issue on linux

    return


def CheckCRC( video_obj, crc_list ):
    if verbose:
        print( "Checking Hash: " + video_obj.filename + ".crc" )

    video_crc_path = os.path.join( root_folder, "crcs", video_obj.filename + ".crc" )

    if os.path.isfile(video_crc_path):
        with open(video_crc_path, mode="r", encoding="utf-8") as file:
            crc_file = file.read().splitlines()

        valid_crcs = []
        for video_crc in crc_file:
            if video_crc not in crc_list:
                # print("Invalid Hash: " + video_obj.filename + ".crc")
                return True
            else:
                valid_crcs.append( video_crc )

        else:
            if valid_crcs != crc_list:
                if verbose:
                    print( "    Not all Hash's validated" )
                return True
            return False
    else:
        # print("Hash File does not exist: " + video_crc_path)
        return True


def GetCRC(string):
    return hashlib.md5(string.encode('utf-8')).hexdigest()


def MakeCRCFile( video_name, crc_list ):
    video_crc_path = os.path.join(root_folder, "crcs")
    CreateDirectory( video_crc_path )
    video_crc_path += os.sep + video_name + ".crc"

    with open( video_crc_path, mode="w", encoding="utf-8" ) as crc_file:
        crc_file.write( '\n'.join(crc_list) )
    return


def GetDateModified( file ):
    if os.name == "nt":
        return os.path.getmtime(file)
    else:
        return os.stat(file).st_mtime


def ReplaceDateModified( file, mod_time ):
    if verbose:
        print( "Replacing Date Modified" )
    os.utime( file, (mod_time, mod_time) )
    
    
def main():
    config_blocks = lexer.ReadFile(config_filepath)

    # base_output_folder = config_folder + "output" + os.sep
    base_output_folder = "output" + os.sep

    if os.sep not in config_filepath:
        config_folder = os.getcwd() + os.sep
    else:
        config_folder = config_filepath.rsplit( os.sep, 1 )[0] + os.sep

    # root_folder, config_blocks, output_folder, config_folder, final_encode

    video_list, base_output_folder = ParseConfig(config_blocks, base_output_folder, config_folder)

    PrintTimestampsFile(video_list, base_output_folder)

    StartEncodingVideos(video_list)

    # would be cool to add crc checking for each time range somehow

    print("Finished")
    print("---------------------------------------------------------------\n")


if __name__ == "__main__":
    # Setup global vars
    root_folder = os.path.dirname(os.path.realpath(__file__)) + os.sep
    config_filepath = FindCommandValue("--config", "-c")
    ffmpeg_bin = FindCommandValue("--ffmpeg_bin", "-ff")
    final_encode = FindCommand("/final", "/f")
    verbose = FindCommand("/verbose", "/v")
    raw_ffmpeg = FindCommand("/raw_ffmpeg", "/raw")

    if ffmpeg_bin:
        if not ffmpeg_bin.endswith(os.sep):
            if ffmpeg_bin.endswith('"'):
                ffmpeg_bin = ffmpeg_bin.rsplit('"', 1)[0] + os.sep
            else:
                ffmpeg_bin = ffmpeg_bin + os.sep
    else:
        # default ffmpeg bin path
        ffmpeg_bin = "D:/demez_archive/video_editing/ffmpeg/current/bin/"

    main()

