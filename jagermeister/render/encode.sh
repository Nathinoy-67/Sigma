#!/usr/bin/env bash
# Encode rendered frames + soundtrack into the deliverables:
#   out/jagermeister-the-hunters-hour.mp4         1080p · 2-pass ~7 Mbps (grain-friendly)
#   out/jagermeister-the-hunters-hour-share.mp4   1080p · 2-pass ~4.2 Mbps (< 30 MB, for messaging apps)
# usage: bash render/encode.sh [frames_dir]
set -euo pipefail
cd "$(dirname "$0")/.."
FR="${1:-frames}"
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
    -af "afade=t=out:st=49.6:d=0.4" -t 50 -movflags +faststart \
    -metadata title="Jägermeister — The Hunter's Hour (spec film)" "$out"
  echo "wrote $out ($(du -h "$out" | cut -f1))"
}

encode out/jagermeister-the-hunters-hour.mp4 "null" 7M 256k
encode out/jagermeister-the-hunters-hour-share.mp4 "null" 4200k 160k
rm -rf "$PL"
