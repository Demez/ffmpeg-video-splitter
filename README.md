# ffmpeg-video-splitter
Uses time stamps in a file to determine what to keep in a video

Example usage of the timestamps file (any name and extension you want it to be) is in timestamps.txt

Example command line usage:

```
py ffmpeg_video_splitter.py --config "PATH_TO_CONFIG" --ffmpeg_bin "PATH_TO_FFMPEG_BIN" [/final] [/verbose]
```

Commands:

`-c` or `--config` - set the path to the timestamp file

`-ff` or `--ffmpeg_bin` - set the path to the ffmpeg bin directory

`/f` or `/final` - sets ffmpeg to use h265 encoding instead of quick h264 encoding by default

`/v` or `/verbose` - enable verbose output

