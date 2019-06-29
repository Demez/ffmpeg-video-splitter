import os, sys
import subprocess
import datetime

# ------------------------------------------------------------------------------------------------------------------------------------------------
# FFMpeg Video Splitter
# 
# what an awful name
# 
# some boring explanation i can't write right now
# i also need to upload this to github aaaa
# 
# HOW TO USE: you look at how i use it and figure it out yourself future me
# 
# Made by Demez, 05/17/2019
# ------------------------------------------------------------------------------------------------------------------------------------------------
# IDEAS:
# 
# - add a setting for selecting a monitor if it's mkv, check if it's the 16:9 and 5:4 monitor or two 16:9 monitors by the resolution
# - add support for multiple files to be merged as one
# - change title bar for the video
# - add an option minimize the ffmpeg output so it only shows the progress, this would be REALLY nice
# - add ffprobe support for audio channel checking
# - Clean up ffmpeg output SOMEHOW
# - and also clean up the rest of the output
# - allow the top to update in another thread as it's running
# ------------------------------------------------------------------------------------------------------------------------------------------------

def FindArgument( search, return_value = False ):
    if search in sys.argv:
        index = 0

        for arg in sys.argv:
            if search == sys.argv[index]:
                if return_value:
                    return sys.argv[ index + 1 ]
                else:
                    return True

            index += 1
    else:
        return False

def RemoveComments( line ):
    line_new = line.split( "//", 1 )[0] # comment type 1
    line_new = RemoveMultiLineComments( line_new )
    return line_new

def RemoveMultiLineComments( line ):

    global in_multiline_comment

    if in_multiline_comment == True:
        commment_end = line.find( "*/" )

        if commment_end == -1:
            return None
        else:
            commment_end += 2 # end comment takes up 2 characters

            line_new = line[commment_end:]

            if line_new.find( "/*" ) != -1:
                # might close and open a new mulit-line comment in the same line
                line_new = FindMultiLineCommentStart( line_new )

            in_multiline_comment = False

            line_new = FindMultiLineCommentStart( line_new )
            return line_new

    line_new = FindMultiLineCommentStart( line )

    return line_new

def FindMultiLineCommentStart( line ):
    global in_multiline_comment

    commment_start = line.find( "/*" )

    if commment_start != -1:
        commment_end = line.find( "*/" )

        line_new = line[:commment_start]

        if commment_end != -1:
            commment_end += 2 # end comment takes up 2 characters

            #line_new = line_new.split( "/*" )

            line_new = line[:commment_start] + line[commment_end:]

            if line_new.find( "/*" ) != -1:
                line_new = RemoveMultiLineComments( line_new )

        else:
            in_multiline_comment = True

        return line_new
    return line

# only removes tabs, new lines, and makes sure the output after that isn't empty
def RemoveExtraCharacters( line ):

    new_line = ''.join( line.split( "\t" ) )
    new_line = ''.join( new_line.split( "\n" ) )

    if new_line != '':
        return new_line
    return None

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

# am i disabled
def ParseLine( line ):

    global in_file_settings
    global file_index
    global file_name
    global input_file_folder

    if line == "{":
        in_file_settings = True
        file_index = 0
        return

    if line == "}": 
        in_file_settings = False
        file_index = 0
        file_name = ""
        return

    if in_file_settings == False:

        # could be an empty line, so the filename has to be in quotes
        if '"' in line:
            # new video file
            quote_split = line.split( '"' ) # probably a bad idea, change this to split it by this
            file_name = quote_split[1]

            if os.sep in file_name:
                input_file_folder = file_name.split( os.sep )[0] + os.sep
                file_name = file_name.split( os.sep )[1]

            elif '/' in file_name:
                input_file_folder = file_name.split( '/' )[0] + os.sep
                #root_dir = root_dir + file_name.split( '/' )[0] + os.sep
                file_name = file_name.split( '/' )[1]

            CheckIfDictExists( ffmpeg_split_dict, file_name, "dict" )
            
            #print( file_name )

    else:
        quote_split = line.split( '"' ) # probably a bad idea, change this to split it by this
        
        start = quote_split[1]
        end = quote_split[3]

        sub_clip = "sub_clip_" + str( file_index )
        CheckIfDictExists( ffmpeg_split_dict[ file_name ], sub_clip, "list" )

        # add the start and end times
        ffmpeg_split_dict[ file_name ][ sub_clip ].append( start )
        ffmpeg_split_dict[ file_name ][ sub_clip ].append( end )

        # increment this
        file_index += 1

#def ParseLineV2( line ):

# --------------------------------------------------------------------------------------------------------

config_file = FindArgument( "-config", True )
ffmpeg = FindArgument( "-ffmpeg", True )
final_encode = FindArgument( "/final" )
slightly_smaller_filesize = FindArgument( "/small_size" )

root_dir = config_file.rsplit( os.sep, 1 )[0] + os.sep

global ffmpeg_split_dict
ffmpeg_split_dict = {}

# wow
file_index = 0
input_file_folder = ""
file_name = ""
in_file_settings = False
in_multiline_comment = False

# main
with open( config_file, mode = "r", encoding = "utf-8" ) as config:

    for line in config:

        # get rid of any comments
        line_new = RemoveComments( line )

        if line_new == None:
            continue

        line_new = RemoveExtraCharacters( line_new )

        if line_new == None:
            continue

        #print( line_new )

        ParseLine( line_new )
         
# ========================================================================================================
# ok now we can throw this stuff into ffmpeg

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
    if not os.path.isdir( directory ):
        os.mkdir( directory )
        
def RemoveDirectory( directory ):
    if os.path.isdir( directory ):
        os.rmdir( directory )

def RunFFMpegConCat( sub_video_list, output_video ):

    with open ( "temp.txt", "w", encoding = "utf-8" ) as temp_file:
        for sub_video in sub_video_list:
            # fix the folder seperators on windows only because windows bad
            if os.name == "nt":
                sub_video = sub_video.replace( "\\", "\\\\" )
            
            temp_file.write( "file '" + sub_video + "'\n" )

    ffmpeg_command = []
    input_list = []

    ffmpeg_command.append( ffmpeg )
    ffmpeg_command.append( "-y" )
    ffmpeg_command.append( "-safe 0" )

    ffmpeg_command.append( "-f concat" )
    ffmpeg_command.append( "-i temp.txt" ) # i wish i didn't need this but i do, ugh

    ffmpeg_command.append( "-c copy" )
    ffmpeg_command.append( "-map 0" )

    # output file
    ffmpeg_command.append( '"' + output_video + '"' )

    subprocess.run( ' '.join( ffmpeg_command ) )
    
    os.remove( "temp.txt" )

def RunFFMpegSubVideo( video, obs_replay_buffer, output_name, start_time, length_time ):

    ffmpeg_command = []

    ffmpeg_command.append( ffmpeg )
    ffmpeg_command.append( "-y" )
    ffmpeg_command.append( "-ss" )
    ffmpeg_command.append( start_time )
    ffmpeg_command.append( '-i "' + video + '"' )

    # TODO: add support for using ffprobe to get info of the audio channels of the video
    if obs_replay_buffer:
        ffmpeg_command.append( "-filter_complex \"[0:a:1][0:a:2]amerge[out]\"" )
        ffmpeg_command.append( "-map \"[out]\"")
    else:
        # need to check if the audio clip only has one track or not with ffprobe
        ffmpeg_command.append( "-filter_complex \"[0:a:0][0:a:1]amerge[out]\"" )
        ffmpeg_command.append( "-map \"[out]\"")
        #ffmpeg_command.append( "-map 0:a" )
        
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
    ffmpeg_command.append( length_time )

    # output file
    ffmpeg_command.append( '"' + output_name + '"' )

    subprocess.run( ' '.join( ffmpeg_command ) )

for video in ffmpeg_split_dict:
    # may add an exclude list here later

    index = 0

    video_name = video.rsplit( ".", 1 )[0]
    temp_path = root_dir + "TEMP_SPLIT" + os.sep
    out_dir = root_dir + "concat" + os.sep
    CreateDirectory( temp_path )
    CreateDirectory( out_dir )

    for sub_clip in ffmpeg_split_dict[ video ]:

        start = SplitTime( ffmpeg_split_dict[ video ][ sub_clip ][0] )
        end = SplitTime( ffmpeg_split_dict[ video ][ sub_clip ][1] )

        #dt_start = datetime.timedelta( hours = start[ "hr" ], minutes = start[ "min" ], seconds = start[ "sec" ], milliseconds = start[ "ms" ] )
        dt_start = datetime.timedelta( hours = start[ "hr" ], minutes = start[ "min" ], seconds = start[ "sec" ] )
        #dt_end = datetime.timedelta( hours = end[ "hr" ], minutes = end[ "min" ], seconds = end[ "sec" ], milliseconds = end[ "ms" ] )
        dt_end = datetime.timedelta( hours = end[ "hr" ], minutes = end[ "min" ], seconds = end[ "sec" ] )

        time_difference = dt_end.total_seconds() - dt_start.total_seconds()

        dt_diff = datetime.timedelta( seconds = time_difference )
        
        # we need to make sure this outputs to an mkv file
        #main_audio = root_dir + "quad_audio" + os.sep + video_name + ".mka"
        if video.endswith( ".mkv" ):
            RunFFMpegSubVideo( root_dir + input_file_folder + video, True, temp_path + "sub_video_" + str( index ) + ".mkv", str( dt_start ), str( dt_diff ) )
        else:
            RunFFMpegSubVideo( root_dir + input_file_folder + video, False, temp_path + "sub_video_" + str( index ) + ".mkv", str( dt_start ), str( dt_diff ) )

        index += 1

    # ok, now combine the sub videos together
    sub_video_list = []
    while( len( sub_video_list ) < index ):
                                                                         # lol
        sub_video_list.append( temp_path + "sub_video_" + str( len( sub_video_list ) ) + ".mkv" )

    RunFFMpegConCat( sub_video_list, out_dir + video_name + ".mkv" )

RemoveDirectory( temp_path )

print( "\n---------------------------------------------------------------" )
print( "ok done" )
print( "---------------------------------------------------------------\n" )

