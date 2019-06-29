# ffmpeg-video-cutter
Uses time stamps in a file to determine what to keep in a video

Example usage of the timestamps file (any name and extension you want it to be) is in timestamps.txt

Example command line usage:

```
py -config "PATH_TO_CONFIG" -ffmpeg "PATH_TO_FFMPEG" [/final]
```

`/final` sets ffmpeg to use h265 encoding instead of quick h264 encoding by default
