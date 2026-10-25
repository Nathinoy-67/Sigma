#!/bin/bash
# Relaunch the render queue (and the plunge sim if unfinished) after a container restart.  Everything is resumable.
cd "$(dirname "$0")"
if ! grep -q "done:" ../frames/sim2.log 2>/dev/null; then
  nohup nice -n 5 /home/user/tools/bpy45-venv/bin/python sims/mpm_plunge.py --out ../frames/sim2 --dx 0.001 --ppc 4 >> ../frames/sim2.log 2>&1 &
fi
nohup bash render_queue.sh "${1:-queue_rest.txt}" >> ../frames/queue.log 2>&1 &
