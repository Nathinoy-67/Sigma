#!/usr/bin/env bash
# Encode rendered frames + soundtrack into the deliverables:
#   out/jagermeister-the-hunters-hour.mp4         1080p · 2-pass ~7 Mbps (grain-friendly)
#   out/jagermeister-the-hunters-hour-share.mp4   1080p · 2-pass ~3.6 Mbps (< 30 MB, for messaging apps)
#   out/jagermeister-the-hunters-hour-hevc.mp4    1080p HEVC · 2-pass ~3.7 Mbps (< 30 MB, highest fidelity; iPhone/modern Android)
# usage: bash render/encode.sh [frames_dir]
set -euo pipefail
cd "$(dirname "$0")/.."
FR="${1:-frames}"
DUR=60                                   # film length (s); the audio fades over its last 0.6 s
AFADE="afade=t=out:st=$(echo "$DUR - 0.6" | bc):d=0.6"
mkdir -p out
PL="$(mktemp -d)"

encode() { # out, scale filter, video bitrate, audio bitrate
  local out="$1" vf="$2" vb="$3" ab="$4"
  local kbps="${vb%k}"; [[ "$vb" == *M ]] && kbps=$(( ${vb%M} * 1000 ))
  local vmax="$(( kbps * 2 ))k"
  local vopt=(-vf "$vf" -c:v libx264 -preset slow -tune film
    -x264-params "aq-mode=3:aq-strength=0.9:keyint=60:min-keyint=30" -b:v "$vb" -maxrate "$vmax" -bufsize "$vmax"
    -pix_fmt yuv420p -profile:v high -level 4.1 -passlogfile "$PL/x264")
  ffmpeg -y -hide_banner -loglevel error -framerate 30 -i "$FR/f%05d.jpg" "${vopt[@]}" -pass 1 -an -f null /dev/null
  ffmpeg -y -hide_banner -loglevel error -framerate 30 -i "$FR/f%05d.jpg" -i audio/soundtrack.wav -map 0:v -map 1:a \
    "${vopt[@]}" -pass 2 -c:a aac -b:a "$ab" -ar 48000 \
    -af "$AFADE" -t "$DUR" -movflags +faststart \
    -metadata title="Jägermeister — The Hunter's Hour (spec film)" "$out"
  echo "wrote $out ($(du -h "$out" | cut -f1))"
}

encode out/jagermeister-the-hunters-hour.mp4 "null" 7M 256k
encode out/jagermeister-the-hunters-hour-share.mp4 "null" 3600k 128k

# HEVC (hvc1-tagged so Apple devices play it natively)
XP="aq-mode=3:psy-rd=2.0:psy-rdoq=1.0:keyint=60:min-keyint=30:stats=$PL/x265.log:log-level=error"
ffmpeg -y -hide_banner -loglevel error -framerate 30 -i "$FR/f%05d.jpg" -c:v libx265 -preset slow -b:v 3700k \
  -x265-params "pass=1:$XP" -pix_fmt yuv420p -an -f null /dev/null
ffmpeg -y -hide_banner -loglevel error -framerate 30 -i "$FR/f%05d.jpg" -i audio/soundtrack.wav -map 0:v -map 1:a \
  -c:v libx265 -preset slow -b:v 3700k -x265-params "pass=2:$XP" -pix_fmt yuv420p -tag:v hvc1 \
  -c:a aac -b:a 160k -ar 48000 -af "$AFADE" -t "$DUR" -movflags +faststart \
  -metadata title="Jägermeister — The Hunter's Hour (spec film)" out/jagermeister-the-hunters-hour-hevc.mp4
echo "wrote out/jagermeister-the-hunters-hour-hevc.mp4 ($(du -h out/jagermeister-the-hunters-hour-hevc.mp4 | cut -f1))"
rm -rf "$PL"
