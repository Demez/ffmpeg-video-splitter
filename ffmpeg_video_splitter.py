import os, sys
import subprocess
import datetime

# ------------------------------------------------------------------------------------------------------------------------------------------------
# FFMpeg Video Splitter
# 
# what an awful name
# 
# some boring explanation i can't write right now
# 
# HOW TO USE: you look at how i use it and figure it out yourself future me
#
# ok now looking at this after remaking vpc in python, this script is fucking awful, i should really make a v2 version with some stuff from this
# 
# Made by Demez, 05/17/2019
# ------------------------------------------------------------------------------------------------------------------------------------------------
# IDEAS:
# 
# - add a setting for selecting a monitor if it's mkv, check if it's the 16:9 and 5:4 monitor or two 16:9 monitors by the resolution
# - change title bar for the video
# - add an option minimize the ffmpeg output so it only shows the progress, this would be REALLY nice
# - Clean up ffmpeg output SOMEHOW
# - allow the top to update in another thread as it's running
# ------------------------------------------------------------------------------------------------------------------------------------------------
        
def FindArgument( search, return_value = False ):
    if search in sys.argv:
        if return_value:
            return sys.argv[ sys.argv.index( search ) + 1 ]
        else:
            return True
    else:
        return False
    
def GetArgumentValue( search ):
    if search in sys.argv:
        return sys.argv[ sys.argv.index( search ) + 1 ]
    else:
        return False
# ------------------------------------------------------------------------------------------------------------------------------------------------
# Timestamp File Parser Functions

def RemoveCommentsAndFixLines( config ):

    line_num = 0
    while line_num < len( config ):
        config[ line_num ] = config[ line_num ].split( "//", 1 )[0] # comment type 1
        line_num += 1

    return RemoveMultiLineCommentsAndFixLines( config )


def RemoveMultiLineCommentsAndFixLines( config ):

    in_comment = False

    # split each string by "/" and check if the start and end characters in each item in the split string is "*"
    # and some other stuff
    line_num = 0
    while line_num < len( config ):

        line_split = config[ line_num ].split( "/" )

        item_num = 0
        while item_num < len( line_split ):
            if line_split[ item_num ].startswith( "*" ):

                if line_split[ item_num ].endswith( "*" ):
                    del line_split[ item_num ]
                    in_comment = False

                # the comment goes over multiple lines
                else:
                    del line_split[ item_num ]
                    in_comment = True
            elif in_comment:
                del line_split[ item_num ]
            else:
                item_num += 1

        # BUG: if there is an invalid string like this: '/*     */  invalid string  /* comment */    /*'
        # it will result in this: '/  invalid string  /'
        # due to joining the split line with '/'
        # so just fix it by running this function here lmao
        config[ line_num ] = FixLineCharacters( '/'.join( line_split ) )
        line_num += 1

    return config

# removes tabs, new lines, makes sure the output after that isn't empty
# also removes spaces in between quotes
def FixLineCharacters( line ):

    line = ''.join( line.split( "\t" ) )
    line = ''.join( line.split( "\n" ) )
    
    in_quote = False
    new_line = ""

    # remove spaces in between quotes by checking each character and checking if we are in quote or not
    for char in line:
        if char == "\"":
            in_quote = not in_quote
            new_line = new_line + char
            continue

        if in_quote or char == "{" or char == "}":
            new_line = new_line + char

        #if char == " " and not in_quote:
        #    continue
        #else:
        #    new_line = new_line + char

    # now fix any incorrect path seperators
    # TODO: set up for posix
    if os.name == "nt":
        if '/' in new_line:
            # split by "/" and then join it right after with the correct character
            new_line = '\\'.join( new_line.split( '/' ) ) 

    return new_line

# this is fucking disgusting probably
def CheckIfDictExists( dictionary, key, value_type ):

    try:
        dictionary[ key ]
    except KeyError:
        if value_type == "dict":
            dictionary[ key ] = {}
        elif value_type == "list":
            dictionary[ key ] = []
        elif value_type == "str":
            dictionary[ key ] = ""

# TODO: add support for full filepaths, then you can delete the above
# also clean up the global vars if you can
# maybe rework this to account for the whole config?
# it might be a bit cleaner, but i really don't feel like it just after rewriting this
def ParseLine( line, line_number ):

    global sub_block_num
    global current_block
    global filename
    global video_blocks
    global file_index
    global out_folder
    global out_folder_line

    if sub_block_num == 0:
        file_index = 0

    if '"' in line:

        # split the line and check string by string
        line_split = line.split( '"' )

        str_index = 0
        while str_index < len( line_split ):

            string = line_split[ str_index ]

            # key option
            if string == "output_folder":
                if out_folder == '':
                    out_folder = line_split[ str_index + 2 ]
                    out_folder_line = line_number
                else:
                    print( "Warning: output_folder defined on lines " + str(out_folder_line) + " and " + str(line_number)  )
                return # nothing else should be in this line
            
            # no other keys, so it's a new video file

            if "{" in string:
                for char in string:
                    if char == "{":
                        sub_block_num += 1
                str_index += 1
                continue # skip to the next string
            elif "}" in string:
                for char in string:
                    if char == "}":
                        sub_block_num -= 1
                str_index += 1
                continue
            elif string == '' or string == ',': # comma is here just to make the txt file neater, completely optional lmao
                str_index += 1
                continue

            if sub_block_num == 0:
                filename = string
                CheckIfDictExists( video_blocks, filename, "dict" )

            elif sub_block_num == 1:
                
                current_block = string

                # TODO: replace the ":" check with quote split, if there is one value, it's a block
                # otherwise, it's a key and a value
                # is it actually a timestamp?
                # check for os.sep because it could be an absolute path
                if ":" in string and not os.sep in string:
                    CheckIfDictExists( video_blocks[ filename ], filename, "dict" )

                    sub_clip = "sub_clip_" + str( file_index )
                    CheckIfDictExists( video_blocks[ filename ][ filename ], sub_clip, "list" )

                    # add the timestamp
                    video_blocks[ filename ][ filename ][ sub_clip ].append( line_split[ str_index ] )
                    video_blocks[ filename ][ filename ][ sub_clip ].append( line_split[ str_index + 2 ] )
                    str_index += 2 # skip to the end timestamp
                    file_index += 1
                else:
                    CheckIfDictExists( video_blocks[ filename ], string, "dict" )

            elif sub_block_num == 2:

                sub_clip = "sub_clip_" + str( file_index )
                CheckIfDictExists( video_blocks[ filename ][ current_block ], sub_clip, "list" )

                # add the timestamp
                video_blocks[ filename ][ current_block ][ sub_clip ].append( line_split[ str_index ] )
                video_blocks[ filename ][ current_block ][ sub_clip ].append( line_split[ str_index + 2 ] )
                str_index += 2 # skip to the end timestamp
                file_index += 1

            str_index += 1

                
    elif "{" in line:
        for char in line:
            if char == "{":
                sub_block_num += 1

    elif "}" in line:
        for char in line:
            if char == "}":
                sub_block_num -= 1

# ------------------------------------------------------------------------------------------------------------------------------------------------
# FFMpeg Function Stuff

def SplitTime( timestamp ):
    time_split = timestamp.split( ":" )
    time_split.reverse() 

    time = {}
        
    #time[ "ms" ] = int( time_split[0].split( "." )[1] )
    #time[ "sec" ] = int( time_split[0].split( "." )[0] )
    time[ "sec" ] = float( time_split[0] )
    time[ "min" ] = int( time_split[1] )
    time[ "hr" ] = int( time_split[2] )

    return time

def CreateDirectory( directory ):
    if not os.path.exists( directory ):
        os.makedirs( directory )
        
def RemoveDirectory( directory ):
    if os.path.isdir( directory ):
        os.rmdir( directory )

def RunFFMpegConCat( sub_video_list, out_video ):

    with open ( "temp.txt", "w", encoding = "utf-8" ) as temp_file:
        for sub_video in sub_video_list:
            # fix the folder seperators on windows only because windows bad
            if os.name == "nt":
                sub_video = sub_video.replace( "\\", "\\\\" )
            
            temp_file.write( "file '" + sub_video + "'\n" )

    ffmpeg_command = []
    input_list = []

    ffmpeg_command.append( ffmpeg_bin + "ffmpeg" )
    ffmpeg_command.append( "-y" )
    ffmpeg_command.append( "-safe 0" )

    ffmpeg_command.append( "-f concat" )
    ffmpeg_command.append( "-i temp.txt" ) # i wish i didn't need this but i do, ugh

    ffmpeg_command.append( "-c copy" )
    ffmpeg_command.append( "-map 0" )

    # output file
    ffmpeg_command.append( '"' + out_video + '"' )

    #sys.stdout.write( "Creating Output Video... " )

    #subprocess.run( ' '.join( ffmpeg_command ), shell = True )

    RunFFMpeg( ' '.join( ffmpeg_command ) )
    
    #sys.stdout.write( "Finished\n" )
    print( "Created Output Video" + "\n-----------------------------------------------------------" )

    os.remove( "temp.txt" )

def RunFFMpegSubVideo( in_video, out_video, time_start, time_length, time_end ):

    ffmpeg_command = []

    ffmpeg_command.append( ffmpeg_bin + "ffmpeg" )
    ffmpeg_command.append( "-y" )
    ffmpeg_command.append( "-ss" )
    ffmpeg_command.append( time_start )
    ffmpeg_command.append( '-i "' + in_video + '"' )

    # get audio track count
    audio_tracks = GetAudioTrackCount( in_video )

    # this is really just a hardcoded hack since this is what i use it for lmao
    if audio_tracks == 5:
        ffmpeg_command.append( "-filter_complex \"[0:a:1][0:a:2]amerge[out]\"" )
        ffmpeg_command.append( "-map \"[out]\"")
    elif audio_tracks == 2:
        # need to check if the audio clip only has one track or not with ffprobe
        ffmpeg_command.append( "-filter_complex \"[0:a:0][0:a:1]amerge[out]\"" )
        ffmpeg_command.append( "-map \"[out]\"")
    else:
        ffmpeg_command.append( "-map 0:a" )
        
    ffmpeg_command.append( "-map 0:v" )

    if final_encode:
        ffmpeg_command.append( "-c:v libx265" )
        ffmpeg_command.append( "-crf 10" )
        ffmpeg_command.append( "-preset medium" ) # maybe slow actually? idk
    else:
        ffmpeg_command.append( "-c:v libx264" )
        ffmpeg_command.append( "-crf 24" )
        ffmpeg_command.append( "-preset ultrafast" )

    ffmpeg_command.append( "-c:a flac" )

    ffmpeg_command.append( "-t" )
    ffmpeg_command.append( time_length )

    # output file
    ffmpeg_command.append( '"' + out_video + '"' )

    file_name = in_video.rsplit( os.sep, 1 )[1]
    print( "Splitting: " + file_name )

    global verbose
    if verbose:
        print( "Start: " + time_start + " - End: " + time_end )

    # TODO: move all the stuff below into it's own function
    RunFFMpeg( ' '.join( ffmpeg_command ), time_length )

    return

def RunFFMpeg( cmd, total_time = None ):
    ffmpeg_run = subprocess.Popen( cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True )

    # TODO: 
    # - do i need to check for any errors? or is that taken care of with stderr going directly out?
    # - maybe change it so it updates the same line?
    for line in ffmpeg_run.stdout:

        if total_time != None:
            if "time=" in line:
                # use the total time range and divide it by ffmpeg's current time in the encode to get a percentage
                line_split = line.split( "time=" )[1]
                current_time_str = line_split.split( " bitrate=" )[0]
                percentage = GetPercent( current_time_str, total_time, 2 )
                #print( str( percentage ) + "%" )
                UpdateProgressBar( percentage, 45 )

                # IDEA: replace the progress bar with "\n" once it's done?

    if total_time != None:
        print( "\n" ) # leave a space for the next one

def GetPercent( current_time_str, total_time_str, round_num ):

    current_time_list = SplitTime( current_time_str )
    total_time_list = SplitTime( total_time_str )

    current_time_dt = datetime.timedelta( hours = current_time_list[ "hr" ], minutes = current_time_list[ "min" ], seconds = current_time_list[ "sec" ] )
    total_time_dt = datetime.timedelta( hours = total_time_list[ "hr" ], minutes = total_time_list[ "min" ], seconds = total_time_list[ "sec" ] )

    return round( ( current_time_dt.total_seconds() / total_time_dt.total_seconds() ) * 100, round_num )

def GetAudioTrackCount( video ):

    ffprobe_command = []

    ffprobe_command.append( ffmpeg_bin + "ffprobe" )
    ffprobe_command.append( "-loglevel error" )
    ffprobe_command.append( "-show_entries stream=codec_type" )
    ffprobe_command.append( "-of csv=p=0" )
    ffprobe_command.append( '"' + video + '"' )

    output = subprocess.check_output( ' '.join( ffprobe_command ), shell = True )

    # now clean up that output and shove it into a list
    stream_list = str( output ).split( "\\n" )

    audio_tracks = 0
    for stream in stream_list:
        if "audio" in stream:
            audio_tracks += 1

    return audio_tracks

# some shitty thing to print what we just parsed
def PrintTimestampsFile( verbose ):
    cmd_bar_line = "-----------------------------------------------------------"

    print( cmd_bar_line )

    if verbose:
        print( "Timestamps File" )
        print( cmd_bar_line )
        for out_video in video_blocks:
            print( out_video )

            for in_video in video_blocks[ out_video ]:
                print( "    " + in_video )

                for sub_video in video_blocks[ out_video ][ in_video ]:
                    print( "        " + video_blocks[ out_video ][ in_video ][ sub_video ][0] + " - " + video_blocks[ out_video ][ in_video ][ sub_video ][1] )

            print( "" )
    print( "Output Folder: " + out_folder )
    if final_encode:
        print( "Final Encode - Using H265 - CRF 10" )
    else:
        print( "Quick Encode - Using H264 - CRF 24" )
    print( cmd_bar_line )

    return


def UpdateProgressBar( percentage, width ):
    percent = percentage / 100

    block = int(round( width * percent ))
    text = "\r{0} {1}%".format( "█" * block + "░"*( width - block ), percentage )
    sys.stdout.write( text )
    sys.stdout.flush()

        
#=========================================================================================================
if __name__ == "__main__":
    
    config_file = FindArgument( "-config", True )
    ffmpeg_bin = FindArgument( "-ffmpeg_bin", True )
    final_encode = FindArgument( "/final" )
    verbose = FindArgument( "/verbose" )

    if ffmpeg_bin != False:
        if not ffmpeg_bin.endswith( os.sep ):
            if ffmpeg_bin.endswith( '"' ):
                ffmpeg_bin = ffmpeg_bin.rsplit( '"', 1 )[0] + os.sep
            else:
                ffmpeg_bin = ffmpeg_bin + os.sep
    else:
        print( "unknown ffmpeg path, use -ffmpeg_bin \"PATH\"" )

    # wow
    file_index = 0
    #in_multiline_comment = False
    sub_block_num = 0
    current_block = ""
    filename = ""
    out_folder = ""
    out_folder_line = 0
    video_blocks = {}

    # Move to ReadTimestampFile( config_file )?
    with open( config_file, mode = "r", encoding = "utf-8" ) as config_read:

        config = config_read.readlines()

        config_new = RemoveCommentsAndFixLines( config )

        line_num = 0
        while line_num < len( config ):
            ParseLine( config[ line_num ], line_num )
            line_num += 1
            
    root_dir = config_file.rsplit( os.sep, 1 )[0] + os.sep
    temp_path = root_dir + "TEMP_SPLIT" + os.sep
    CreateDirectory( temp_path )

    if out_folder == '':
        out_dir = root_dir + "concat" + os.sep
    else:
        # root folder on linux would probably be ./, ~/ means home, right?
        if os.name == "nt" and ":\\" in out_folder:
            out_dir = out_folder + os.sep
        else:
            out_dir = root_dir + out_folder

    PrintTimestampsFile( verbose )

    #StartEncodingVideos()

    # maybe make the progress bar for the whole file?
    for video in video_blocks:

        index = 0
        print( "Output Video: " + video + "\n" )
        for sub_video in video_blocks[ video ]:
            for sub_clip in video_blocks[ video ][ sub_video ]:

                start = SplitTime( video_blocks[ video ][ sub_video ][ sub_clip ][0] )
                end = SplitTime( video_blocks[ video ][ sub_video ][ sub_clip ][1] )

                #dt_start = datetime.timedelta( hours = start[ "hr" ], minutes = start[ "min" ], seconds = start[ "sec" ], milliseconds = start[ "ms" ] )
                dt_start = datetime.timedelta( hours = start[ "hr" ], minutes = start[ "min" ], seconds = start[ "sec" ] )
                #dt_end = datetime.timedelta( hours = end[ "hr" ], minutes = end[ "min" ], seconds = end[ "sec" ], milliseconds = end[ "ms" ] )
                dt_end = datetime.timedelta( hours = end[ "hr" ], minutes = end[ "min" ], seconds = end[ "sec" ] )

                time_difference = dt_end.total_seconds() - dt_start.total_seconds()
                dt_diff = datetime.timedelta( seconds = time_difference )

                if os.sep in sub_video:
                    sub_video_split = sub_video.rsplit( os.sep, 1 )

                    full_path = sub_video_split[0] + os.sep
                    sub_video_name = sub_video_split[1]

                    # would this be "./" on linux?
                    if ":\\" not in full_path and os.name == "nt":
                        full_path = root_dir + full_path
                else:
                    full_path = root_dir
                    sub_video_name = sub_video
        
                RunFFMpegSubVideo( full_path + sub_video_name, temp_path + "sub_video_" + str( index ) + ".mkv", str( dt_start ), str( dt_diff ), str( dt_end ) )

                index += 1

        # ok, now combine the sub videos together
        sub_video_list = []
        while( len( sub_video_list ) < index ):                           # lol
            sub_video_list.append( temp_path + "sub_video_" + str( len( sub_video_list ) ) + ".mkv" )

        if os.sep in video:
            out_video_split = video.rsplit( os.sep, 1 )

            full_out_dir = out_video_split[0] + os.sep
            out_video_name = out_video_split[1].rsplit( ".", 1 )[0]

            if ":\\" not in full_out_dir and os.name == "nt":
                full_out_dir = out_dir + full_out_dir
        else:
            full_out_dir = out_dir
            out_video_name = video.rsplit( ".", 1 )[0]

        CreateDirectory( full_out_dir )

        RunFFMpegConCat( sub_video_list, full_out_dir + out_video_name + ".mkv" )

    # really not needed, and gives an OSError on linux saying it's not empty
    #RemoveDirectory( temp_path )

    print( "Finished" )
    print( "---------------------------------------------------------------\n" )

