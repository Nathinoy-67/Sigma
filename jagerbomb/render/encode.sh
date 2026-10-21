#!/usr/bin/env bash
# Encode rendered frames + soundtrack into the deliverables:
#   out/jagermeister-the-drop.mp4         1080p · 2-pass ~7 Mbps H.264 (grain-friendly master)
#   out/jagermeister-the-drop-share.mp4   1080p · 2-pass ~3 Mbps H.264 (< 30 MB, for messaging apps)
#   out/jagermeister-the-drop-hevc.mp4    1080p HEVC · 2-pass ~3 Mbps (< 30 MB, highest fidelity; iPhone/modern Android)
# Subtitles are burned into the picture; out/jagermeister-the-drop.en.srt carries the same lines.
# usage: bash render/encode.sh [frames_dir]
set -euo pipefail
cd "$(dirname "$0")/.."
FR="${1:-frames}"
DUR=$(node -e "import('./src/timeline.js').then(m => console.log(m.DURATION))")
AFADE="afade=t=out:st=$(echo "$DUR - 0.6" | bc):d=0.6"
TITLE="Jägermeister — The Drop (spec film)"
mkdir -p out
PL="$(mktemp -d)"

encode() { # out, video bitrate, audio bitrate
  local out="$1" vb="$2" ab="$3"
  local kbps="${vb%k}"; [[ "$vb" == *M ]] && kbps=$(( ${vb%M} * 1000 ))
  local vmax="$(( kbps * 2 ))k"
  local vopt=(-c:v libx264 -preset slow -tune film
    -x264-params "aq-mode=3:aq-strength=0.9:keyint=60:min-keyint=30" -b:v "$vb" -maxrate "$vmax" -bufsize "$vmax"
    -pix_fmt yuv420p -profile:v high -level 4.1 -passlogfile "$PL/x264")
  ffmpeg -y -hide_banner -loglevel error -framerate 30 -i "$FR/f%05d.jpg" "${vopt[@]}" -pass 1 -an -f null /dev/null
  ffmpeg -y -hide_banner -loglevel error -framerate 30 -i "$FR/f%05d.jpg" -i audio/soundtrack.wav -map 0:v -map 1:a \
    "${vopt[@]}" -pass 2 -c:a aac -b:a "$ab" -ar 48000 \
    -af "$AFADE" -t "$DUR" -movflags +faststart -metadata title="$TITLE" "$out"
  echo "wrote $out ($(du -h "$out" | cut -f1))"
}

encode out/jagermeister-the-drop.mp4 7M 256k
encode out/jagermeister-the-drop-share.mp4 3000k 128k

# HEVC (hvc1-tagged so Apple devices play it natively)
XP="aq-mode=3:psy-rd=2.0:psy-rdoq=1.0:keyint=60:min-keyint=30:stats=$PL/x265.log:log-level=error"
ffmpeg -y -hide_banner -loglevel error -framerate 30 -i "$FR/f%05d.jpg" -c:v libx265 -preset slow -b:v 3000k \
  -x265-params "pass=1:$XP" -pix_fmt yuv420p -an -f null /dev/null
ffmpeg -y -hide_banner -loglevel error -framerate 30 -i "$FR/f%05d.jpg" -i audio/soundtrack.wav -map 0:v -map 1:a \
  -c:v libx265 -preset slow -b:v 3000k -x265-params "pass=2:$XP" -pix_fmt yuv420p -tag:v hvc1 \
  -c:a aac -b:a 160k -ar 48000 -af "$AFADE" -t "$DUR" -movflags +faststart -metadata title="$TITLE" out/jagermeister-the-drop-hevc.mp4
echo "wrote out/jagermeister-the-drop-hevc.mp4 ($(du -h out/jagermeister-the-drop-hevc.mp4 | cut -f1))"
rm -rf "$PL"
