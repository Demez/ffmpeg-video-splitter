import os
import sys
import re
import subprocess
import datetime
import shutil
import hashlib


# how the awful crc checking works:
# it makes a crc for every time range, input video name, output video name, verbose, and final encode
# and dumps it all to a file if it doesn't exist
# it scans that file to see if any crc matches what we have


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


class VideoFile:
    def __init__(self, filename, root_folder, output_folder, force_file_ext):

        self.output_folder = output_folder

        self.rawpath = os.path.normpath( filename )
        self.path = os.path.normpath( filename )

        if force_file_ext:
            prefix = os.path.splitext(filename)[0]
            if "." not in force_file_ext:
                force_file_ext = "." + force_file_ext
            self.path = os.path.normpath( prefix + force_file_ext )

        if os.sep in self.path:
            self.filename = self.path.rsplit( os.sep, 1 )[1]
        else:
            self.filename = self.path

        self.full_path = os.path.normpath( output_folder + os.sep + self.path )

        self.root_folder = root_folder
        self.input_videos = []

        self.skip = False  # this will be set to true if the crc check fails
        self.crc_list = []

    def AddInputVideo(self, input_video_filename):

        for input_video_obj in self.input_videos:
            if input_video_filename == input_video_obj.rawpath:
                return

        input_video = InputVideoFile( input_video_filename, self.root_folder )
        self.input_videos.append( input_video )

        return

    def AddTimeRange(self, start, end):
        # maybe i should use a filename and get the index instead? idk
        input_video = self.input_videos[-1]
        input_video.AddTimeRange(start, end)

        return


class InputVideoFile:
    def __init__(self, filename, root_folder):
        self.abspath = os.path.normpath( root_folder + os.sep + filename )
        self.filename = self.abspath.rsplit( os.sep, 1 )[1]
        # self.folder = self.abspath.rsplit( os.sep, 1 )[0]
        self.rawpath = filename
        self.time_ranges = []

        self.crc = ''

    def AddTimeRange(self, start, end):
        self.time_ranges.append([ConvertToDateTime(start), ConvertToDateTime(end)])

    def GetTimeRange(self, list_index):
        dt_start = self.time_ranges[list_index][0]
        dt_end = self.time_ranges[list_index][1]
        dt_diff = self.GetTimeDiff(dt_start, dt_end)
        return dt_start, dt_end, dt_diff

    def GetTimeDiff(self, dt_start, dt_end):
        time_difference = dt_end.total_seconds() - dt_start.total_seconds()
        return datetime.timedelta(seconds=time_difference)


class ConfigBlock:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.items = []

    def AddItem( self, item ):
        self.items.append( item )


def ConvertToDateTime(timestamp_str):
    time_split = timestamp_str.split(":")
    time_split.reverse()

    seconds = float(time_split[0])
    minutes = int(time_split[1])
    hours = int(time_split[2])

    time_dt = datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)

    return time_dt


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


def CleanFile(config):

    in_comment = False
    new_config = []
    for line_num, line in enumerate(config):

        # removes all multi-line comments from the line
        line = re.sub( r'/\*.*?\*/', r'', line )

        if in_comment:
            if "*/" in line:
                line = line.split("*/", 1)[1]
                in_comment = False
            else:
                continue

        if "/*" in line:
            line = line.split("/*", 1)[0]
            in_comment = True

        line = line.split("//", 1)[0]

        if not line:
            continue

        # replace tabs with spaces
        # this can cause a lot of spaces to be added, could be bad
        line = ' '.join(line.split("\t"))

        # now split the line by quotes
        line_split = _RemoveQuotesAndSplitLine( line )

        if not line_split:
            continue

        new_config.append( line_split )

    return new_config


# remove quotes in the string if there is any
def _RemoveQuotesAndSplitLine( line ):

    # add a gap in between these if they exist just in case
    # so we can have no spaces in the actual file if we want
    line = line.replace( "{", " { ")
    line = line.replace( "}", " } ")
    line = line.replace( ",", " ")
    line = line.replace( "\"\"", "\" \"")  # add a space in between any quotes that may be right next to each other

    line_split = []
    raw_line_split = line.split(" ")

    str_num = 0
    while str_num < len( raw_line_split ):
        string = raw_line_split[ str_num ]

        if string.startswith( '"' ):

            if string.endswith( '"' ):
                str_len = len( string )
                string = string[ 1: str_len-1 ]

            else:
                quote = string[1:]  # strip the start quote off
                quote_str_num = str_num + 1

                # this will keep adding strings together until one of them ends with a quote
                while not quote.endswith( "\"" ):
                    quote += " " + raw_line_split[ quote_str_num ]
                    quote_str_num += 1

                str_num = quote_str_num - 1
                string = quote[:-1]  # strip the end quote off

        elif not string:
            str_num += 1
            continue

        line_split.append(string)
        str_num += 1

    return line_split


# Re-Formats the config, so no more blocks in one single line
def _FormatConfigBlocks( config ):

    new_config = []
    for line_num, split_line in enumerate( config ):

        if "{" in split_line or "}" in split_line:
            new_split_line = []
            for item in split_line:
                if "{" in item or "}" in item:
                    # what about if the length is over 2?
                    if new_split_line:
                        new_config.append( new_split_line )
                    new_config.append( [item] )
                    new_split_line = []
                elif len(new_split_line) >= 2:
                    new_config.append( new_split_line )
                    new_split_line = []
                    new_split_line.append( item )

                else:
                    new_split_line.append( item )

            # new_config.append( new_split_line )

        else:
            new_config.append( split_line )

    return new_config


def CreateConfigBlocks( config ):
    config_blocks = []

    line_num = 0
    while line_num < len(config):

        line_num, block = CreateConfigBlock(config, line_num)
        block = CreateConfigBlockObject(block)
        config_blocks.append(block)

        continue

    return config_blocks


def CreateConfigBlock( config, line_number ):

    block_depth_num = 0

    block = [config[line_number]]
    if config[line_number] == ['{']:
        block_depth_num = 1

    line_number += 1

    while line_number < len(config):

        current_line = config[ line_number ]

        if len(block[-1]) < 1 and block[-1][-1] != "\\":
            if block_depth_num == 0 and current_line == []:
                break

        if current_line:
            if (current_line == ['{']) or (block_depth_num != 0):
                block.append(current_line)

            elif len(block[-1]) > 1:
                if block_depth_num == 0:
                    # this is a single line block
                    break

            else:
                break

        if "{" in current_line:
            block_depth_num += 1

        if "}" in current_line:
            block_depth_num -= 1

        line_number += 1

    return line_number, block


def CreateConfigBlockObject( block ):

    try:
        value = block[0][1]
    except IndexError:
        value = None

    block_obj = ConfigBlock(block[0][0], value)

    if len(block) > 1:

        block_line_num = 1
        while block_line_num < len(block):

            if block[block_line_num] != [] and block[block_line_num][0] != '{' and block[block_line_num][0] != '}':

                block_line_num, sub_block = CreateConfigBlock(block, block_line_num)

                if isinstance(sub_block, list):
                    sub_block = CreateConfigBlockObject(sub_block)
                    block_obj.AddItem(sub_block)
                    continue

            block_line_num += 1

    return block_obj


def ReadConfig( config_filepath ):
    with open(config_filepath, mode="r", encoding="utf-8") as config_file:
        config = config_file.read().splitlines()

    config = CleanFile( config )
    config = _FormatConfigBlocks( config )
    config_blocks = CreateConfigBlocks( config )

    return config_blocks


def ParseConfig( root_folder, config_blocks, base_output_folder, config_folder, final_encode ):
    if verbose:
        print( "Parsing Config" )

    force_file_ext = False
    video_list = []
    for block_obj in config_blocks:

        if block_obj.key == "base_output_folder" or block_obj.key == "output_folder":
            if os.path.isabs( block_obj.value ):
                base_output_folder = os.path.normpath( block_obj.value ) + os.sep
            else:
                base_output_folder = os.path.normpath( config_folder + block_obj.value ) + os.sep
            full_output_folder = base_output_folder

        elif block_obj.key == "append_output_folder":
            if os.path.isabs( block_obj.value ):
                full_output_folder = os.path.normpath( block_obj.value )
            else:
                full_output_folder = os.path.normpath( base_output_folder + block_obj.value )

        elif block_obj.key == "force_file_ext":
            force_file_ext = block_obj.value

        # is a video file
        else:

            video_file = VideoFile( block_obj.key, config_folder, full_output_folder, force_file_ext )

            if block_obj.items:
                AddInputVideosToVideo( video_file, block_obj )

            video_list.append(video_file)

            video_file.crc_list.append(GetCRC(base_output_folder))
            video_file.crc_list.append( GetCRC( str(final_encode) ) )

            if not os.path.isfile(video_file.full_path):
                continue

            elif not CheckCRC(root_folder, video_file, video_file.crc_list):
                video_file.skip = True

    return video_list, base_output_folder


def AddInputVideosToVideo( video_file, block_obj ):
    for input_video_block in block_obj.items:

        crc_list = []
        # issue - will add multiple of the same input video, ugh
        if ":" in input_video_block.key and not os.sep in input_video_block.key:
            video_file.AddInputVideo( video_file.rawpath )
            video_file.AddTimeRange(input_video_block.key, input_video_block.value)

            crc_list.append( GetCRC(video_file.rawpath) )
            crc_list.append( GetCRC(input_video_block.key) )
            crc_list.append( GetCRC(input_video_block.value) )

        else:
            video_file.AddInputVideo( input_video_block.key )

            for time_range_block in input_video_block.items:
                video_file.AddTimeRange(time_range_block.key, time_range_block.value)

                crc_list.append( GetCRC(time_range_block.key) )
                crc_list.append( GetCRC(time_range_block.value) )

        video_file.crc_list.extend( crc_list )
    return


# some shitty thing to print what we just parsed
def PrintTimestampsFile( video_list, out_folder, final_encode, verbose = False ):
    cmd_bar_line = "-----------------------------------------------------------"

    print( cmd_bar_line )

    if verbose:
        print( "Timestamps File" )
        print( cmd_bar_line )
        for out_video in video_list:
            print( out_video.path )

            for in_video in out_video.input_videos:
                print( "    " + in_video.rawpath )

                for time_range in in_video.time_ranges:
                    print( "        " + str(time_range[0]) + " - " + str(time_range[1]) )

            print( "" )
    print( "Default Output Folder: " + out_folder )
    if final_encode:
        print( "Final Encode - Using H265 - CRF 8" )
    else:
        print( "Quick Encode - Using H264 - CRF 24" )
    print( cmd_bar_line )

    return


def RunFFMpegConCat(sub_video_list, out_video):
    # stuff for ffmpeg concat shit
    with open("temp.txt", "w", encoding="utf-8") as temp_file:
        for sub_video in sub_video_list:
            temp_file.write("file '" + sub_video + "'\n")

    ffmpeg_command = []

    ffmpeg_command.append(ffmpeg_bin + "ffmpeg")
    ffmpeg_command.append("-y")
    ffmpeg_command.append("-safe 0")

    ffmpeg_command.append("-f concat")
    ffmpeg_command.append("-i temp.txt")  # i wish i didn't need this but i do, ugh

    ffmpeg_command.append("-c copy")
    ffmpeg_command.append("-map 0")

    # output file
    ffmpeg_command.append('"' + out_video + '"')

    RunFFMpeg(' '.join(ffmpeg_command))

    # print("Created Output Video")
    print("\n-----------------------------------------------------------")

    os.remove("temp.txt")


def RunFFMpegSubVideo( time_range_number, input_video, temp_video, final_encode, verbose ):

    dt_start, dt_end, dt_diff = input_video.GetTimeRange( time_range_number )
    time_start = str(dt_start)
    time_end = str(dt_end)
    time_diff = str(dt_diff)

    ffmpeg_command = []

    ffmpeg_command.append(ffmpeg_bin + "ffmpeg")
    ffmpeg_command.append("-y")
    ffmpeg_command.append("-ss")
    ffmpeg_command.append(time_start)
    ffmpeg_command.append('-i "' + input_video.abspath + '"')

    # get audio track count
    audio_tracks = GetAudioTrackCount(input_video.abspath)

    # this is really just a hardcoded hack since this is what i use it for lmao
    if audio_tracks == 5:
        ffmpeg_command.append("-filter_complex \"[0:a:1][0:a:2]amerge[out]\"")
        ffmpeg_command.append("-map \"[out]\"")
    elif audio_tracks == 2:
        # need to check if the audio clip only has one track or not with ffprobe
        ffmpeg_command.append("-filter_complex \"[0:a:0][0:a:1]amerge[out]\"")
        ffmpeg_command.append("-map \"[out]\"")
    else:
        ffmpeg_command.append("-map 0:a")

    ffmpeg_command.append("-map 0:v")

    if final_encode:
        ffmpeg_command.append("-c:v libx265")
        ffmpeg_command.append("-crf 8")
        ffmpeg_command.append("-preset slow")  # medium
    else:
        ffmpeg_command.append("-c:v libx264")
        ffmpeg_command.append("-crf 24")
        ffmpeg_command.append("-preset ultrafast")

    ffmpeg_command.append("-c:a flac")

    ffmpeg_command.append("-t")
    ffmpeg_command.append(time_diff)

    # output file
    ffmpeg_command.append('"' + temp_video + '"')

    total_frames = GetTotalFrameCount( dt_diff, GetFrameRate(input_video.abspath) )

    if verbose:
        print("Start: " + time_start + " - End: " + time_end)
        print("Total Frames: " + str(total_frames))

    RunFFMpeg(' '.join(ffmpeg_command), total_frames)

    if verbose:
        print("")  # space in between

    return


def GetFrameRate( video_path ):
    command = [
        ffmpeg_bin + "ffprobe",
        "-v 0",
        "-of csv=p=0",
        "-select_streams v:0",
        "-show_entries stream=r_frame_rate",
        '"' + video_path + '"'
    ]

    output = subprocess.check_output(' '.join(command), shell=True)

    output = str(output).replace( "\\r", "" )
    output = output.replace( "\\n", "" )
    output = output.replace( "\'", "" )
    output = output.replace( "b", "" )

    numerator, denominator = output.split( "/" )

    frame_rate = int(numerator) / int(denominator)

    return frame_rate


def GetTotalFrameCount( dt_time_length, frame_rate ):
    return dt_time_length.total_seconds() * frame_rate


def RunFFMpeg( cmd, total_frames = None ):
    ffmpeg_run = subprocess.Popen( cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True )

    if total_frames:
        UpdateProgressBar( 0.00, 52 )  # start it at 0

    # TODO:
    # - do i need to check for any errors? or is that taken care of with stderr going directly out?
    # - maybe change it so it updates the same line?
    for line in ffmpeg_run.stdout:

        if total_frames:
            if "frame=" in line:
                # use the total time range and divide it by ffmpeg's current time in the encode to get a percentage
                line_split = line.split( "frame= " )[1]
                current_frame = line_split.split( " fps=" )[0]  # wrong
                percentage = GetPercent( int(current_frame),  total_frames, 2 )
                UpdateProgressBar( percentage, 52 )
                # IDEA: replace the progress bar with "\n" once it's done?

    if total_frames:
        UpdateProgressBar(100.0, 52)  # usually it finishes before we can catch the last frame
        # print( "" )  # leave a space for the next one


def GetPercent( current_frame, total_frames, round_num ):
    return round( ( current_frame / total_frames ) * 100, round_num )


def UpdateProgressBar( percentage, width ):
    percent = percentage / 100

    block = int(round( width * percent ))
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

    output = subprocess.check_output( ' '.join( ffprobe_command ), shell = True )

    # now clean up that output and shove it into a list
    stream_list = str( output ).split( "\\n" )

    audio_tracks = 0
    for stream in stream_list:
        if "audio" in stream:
            audio_tracks += 1

    return audio_tracks


def StartEncodingVideos( video_list, final_encode, verbose = False ):

    temp_path = os.path.dirname(os.path.realpath(__file__)) + os.sep + "TEMP" + os.sep
    CreateDirectory(temp_path)

    for output_video in video_list:
        if output_video.skip:
            continue

        MakeCRCFile(root_folder, output_video.filename, output_video.crc_list)
        DeleteFile( output_video.full_path )

        if verbose:
            print(output_video.full_path + "\n")
        else:
            print("Output Video: " + output_video.path + "\n")

        temp_video_list = []
        temp_video_num = 0
        for input_video in output_video.input_videos:

            print("Splitting: " + input_video.filename)

            time_range_number = 0
            while time_range_number < len(input_video.time_ranges):

                temp_video = temp_path + str(temp_video_num) + ".mkv"
                temp_video_list.append( temp_video )

                RunFFMpegSubVideo( time_range_number, input_video, temp_video, final_encode, verbose )
                time_range_number += 1
                temp_video_num += 1

                if time_range_number < len(input_video.time_ranges):
                    print( "" )

        CreateDirectory( output_video.output_folder )

        # now combine all the sub videos together
        RunFFMpegConCat(temp_video_list, output_video.full_path)

    RemoveDirectory(temp_path)  # has an issue on linux

    return


def CheckCRC( root_dir, video_obj, crc_list ):

    if verbose:
        print( "Checking CRC: " + video_obj.filename + ".crc" )

    video_crc_path = os.path.join( root_dir, "crcs", video_obj.filename + ".crc" )

    if os.path.isfile(video_crc_path):
        crc_file = ReadConfig(video_crc_path)  # this might be slowing this down, but idc

        valid_crcs = []
        for crc_line in crc_file:
            video_crc = crc_line.key

            if video_crc not in crc_list:
                print("Invalid CRC: " + video_obj.filename + ".crc")
                return True
            else:
                valid_crcs.append( video_crc )

        else:
            if valid_crcs != crc_list:
                if verbose:
                    print( "    Not all CRC's validated" )
                return True
            return False
    else:
        print("CRC File does not exist: " + video_crc_path)
        return True


def GetCRC(string):
    return hashlib.md5(string.encode('utf-8')).hexdigest()


def MakeCRCFile( root_dir, video_name, crc_list ):

    video_crc_path = os.path.join(root_dir, "crcs")
    CreateDirectory( video_crc_path )
    video_crc_path += os.sep + video_name + ".crc"

    with open( video_crc_path, mode="w", encoding="utf-8" ) as crc_file:
        for crc in crc_list:
            crc_file.write( crc + "\n" )
    return


if __name__ == "__main__":

    config_filepath = FindCommandValue("--config", "-c")
    ffmpeg_bin = FindCommandValue("--ffmpeg_bin", "-ff")
    final_encode = FindCommand("/final", "/f")
    verbose = FindCommand("/verbose", "/v")

    if ffmpeg_bin:
        if not ffmpeg_bin.endswith(os.sep):
            if ffmpeg_bin.endswith('"'):
                ffmpeg_bin = ffmpeg_bin.rsplit('"', 1)[0] + os.sep
            else:
                ffmpeg_bin = ffmpeg_bin + os.sep
    else:
        print("unknown ffmpeg path, use -ffmpeg_bin \"PATH\"")

    config_blocks = ReadConfig( config_filepath )

    root_folder = os.path.dirname(os.path.realpath(__file__))

    if os.sep not in config_filepath:
        config_folder = os.getcwd() + os.sep
    else:
        config_folder = config_filepath.rsplit( os.sep, 1 )[0] + os.sep

    base_output_folder = config_folder + "output" + os.sep

    # root_folder, config_blocks, output_folder, config_folder, final_encode

    video_list, base_output_folder = ParseConfig(root_folder, config_blocks, base_output_folder, config_folder, final_encode)

    PrintTimestampsFile(video_list, base_output_folder, final_encode, verbose)

    StartEncodingVideos(video_list, final_encode, verbose)

    # would be cool to add crc checking for each time range somehow

    print("Finished")
    print("---------------------------------------------------------------\n")


