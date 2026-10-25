#!/bin/bash
# Render queue: one render_shot.py command per line of the queue file (comments with #).  Resumable: finished frames
# are skipped.  Usage: nohup bash v3/blender/render_queue.sh v3/blender/queue_a.txt > v3/frames/queue_a.log 2>&1 &
cd "$(dirname "$0")"
PY=/home/user/tools/blender-venv/bin/python
while IFS= read -r line; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  echo "=== $(date +%H:%M:%S) $line"
  nice -n 15 $PY render_shot.py $line 2>&1 | grep -E "^\[|Error|Traceback" 
done < "$1"
echo "=== $(date +%H:%M:%S) queue done"
