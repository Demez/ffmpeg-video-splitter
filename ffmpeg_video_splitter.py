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
# - change title bar for the video
# - add an option minimize the ffmpeg output so it only shows the progress, this would be REALLY nice
# - Clean up ffmpeg output SOMEHOW
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
    if line_new != None:
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

# removes tabs, new lines, makes sure the output after that isn't empty
# also 
def FixLineCharacters( line ):

    new_line = ''.join( line.split( "\t" ) )
    new_line = ''.join( new_line.split( "\n" ) )
    
    in_quote = False
    new_new_line = "" # nice var name, lmao

    # remove spaces in between quotes by checking each character and checking if we are in quote or not
    for char in new_line:
        if char == "\"":
            in_quote = not in_quote

        if char == " " and not in_quote:
            continue
        else:
            new_new_line = new_new_line + char

    # now fix any incorrect path seperators
    # TODO: set up for posix
    if os.name == "nt":
        if '/' in new_new_line:
            # split by "/" and then join it right after with the correct character
            new_new_line = '\\'.join( new_new_line.split( '/' ) ) 

    if new_new_line != '':
        return new_new_line
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

# TODO: add support for full filepaths, then you can delete the above
# also clean up the global vars if you can
def ParseLine( line ):

    global sub_block_num
    global current_block
    global filename
    global video_blocks
    global file_index
    global out_folder

    if sub_block_num == 0:
        file_index = 0

    if '"' in line:

        # new video file
        # split the line and check string by string
        line_split = line.split( '"' )
        
        # might be a key?
        if line.startswith( "output_folder" ):
            out_folder = ""

        str_index = 0
        while str_index < len( line_split ):

            string = line_split[ str_index ]

            if string == "output_folder":
                out_folder = line_split[ str_index + 2 ]
                return # nothing else should be in this line

        #for string in quote_split:
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
                    str_index += 2 # skip past the end timestamp
                    file_index += 1
                else:
                    CheckIfDictExists( video_blocks[ filename ], string, "dict" )

            elif sub_block_num == 2:

                sub_clip = "sub_clip_" + str( file_index )
                CheckIfDictExists( video_blocks[ filename ][ current_block ], sub_clip, "list" )

                # add the timestamp
                video_blocks[ filename ][ current_block ][ sub_clip ].append( line_split[ str_index ] )
                video_blocks[ filename ][ current_block ][ sub_clip ].append( line_split[ str_index + 2 ] )
                str_index += 2 # skip past the end timestamp
                file_index += 1
                #continue

            str_index += 1

                
    elif "{" in line:
        for char in line:
            if char == "{":
                sub_block_num += 1

    elif "}" in line:
        for char in line:
            if char == "}":
                sub_block_num -= 1

# --------------------------------------------------------------------------------------------------------

config_file = FindArgument( "-config", True )

#if os.name == "nt":
ffmpeg_bin = FindArgument( "-ffmpeg_bin", True )

if ffmpeg_bin != None:
    if not ffmpeg_bin.endswith( os.sep ):
        if ffmpeg_bin.endswith( '"' ):
            ffmpeg_bin = ffmpeg_bin.rsplit( '"', 1 )[0] + os.sep
        else:
            ffmpeg_bin = ffmpeg_bin + os.sep

#if ffmpeg == None:
    # on linux you can just put this in the command line, so if you don't specify -ffmpeg, it will just use this (bad idea?)
    #ffmpeg = "ffmpeg"

final_encode = FindArgument( "/final" )

root_dir = config_file.rsplit( os.sep, 1 )[0] + os.sep

# wow
file_index = 0
in_multiline_comment = False
sub_block_num = 0
current_block = ""
filename = ""
video_blocks = {}

# main
with open( config_file, mode = "r", encoding = "utf-8" ) as config:

    for line in config:

        # get rid of any comments
        line_new = RemoveComments( line )

        if line_new == None:
            continue

        line_new = FixLineCharacters( line_new )

        if line_new == None:
            continue

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

    subprocess.run( ' '.join( ffmpeg_command ), shell = True )
    
    os.remove( "temp.txt" )

def RunFFMpegSubVideo( in_video, out_video, start_time, length_time ):

    ffmpeg_command = []

    ffmpeg_command.append( ffmpeg_bin + "ffmpeg" )
    ffmpeg_command.append( "-y" )
    ffmpeg_command.append( "-ss" )
    ffmpeg_command.append( start_time )
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
    ffmpeg_command.append( length_time )

    # output file
    ffmpeg_command.append( '"' + out_video + '"' )

    subprocess.run( ' '.join( ffmpeg_command ), shell = True )

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

temp_path = root_dir + "TEMP_SPLIT" + os.sep
out_dir = root_dir + "concat" + os.sep

CreateDirectory( temp_path )

# some shitty thing to print what we just parsed
for out_video in video_blocks:
    print( out_video )

    for in_video in video_blocks[ out_video ]:
        print( "    " + in_video )

        for sub_video in video_blocks[ out_video ][ in_video ]:
            timerange = video_blocks[ out_video ][ in_video ][ sub_video ][0] + " - " + video_blocks[ out_video ][ in_video ][ sub_video ][1]
            print( "        " + timerange )
    print( "" )

for video in video_blocks:

    index = 0
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

                if ":\\" not in full_path and os.name == "nt":
                    full_path = root_dir + full_path
            else:
                full_path = root_dir
                sub_video_name = sub_video
        
            RunFFMpegSubVideo( full_path + sub_video_name, temp_path + "sub_video_" + str( index ) + ".mkv", str( dt_start ), str( dt_diff ) )

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

print( "\n---------------------------------------------------------------" )
print( "Finished" )
print( "---------------------------------------------------------------\n" )

