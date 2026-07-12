#!/bin/bash
# session_terminal.command — scripted ground-truth screen session (the referee's stimulus).
#
# Runs INSIDE a visible Terminal window (open it with `open session_terminal.command`) and
# drives known activity phases at known times, logging each phase start (epoch ms) to
# /tmp/screen_eval_truth.log. The recorder captures the screen meanwhile; eval/score.py then
# compares the recorder's ACTIVITY labels against this log.
#
# Phases: still(7s) -> typing(~8s) -> still(7s) -> scrolling(~7s) -> still(7s) -> video(~9s)

T=/tmp/screen_eval_truth.log
log() { echo "$(python3 -c 'import time; print(int(time.time()*1000))') $1" >> "$T"; }
rm -f "$T"

clear
log begin_still
sleep 7

log begin_typing
for i in $(seq 1 12); do
  echo "typing line $i — the quick brown fox jumps over the lazy dog"
  sleep 0.65
done

log begin_still
sleep 7

log begin_scrolling
for i in $(seq 1 55); do
  echo "scroll filler line $i ................................................."
  sleep 0.12
done

log begin_still
sleep 7

log begin_video
for i in $(seq 1 85); do
  clear
  head -c 4000 /dev/urandom | base64 | fold -w 110 | head -40
  sleep 0.1
done

log end
sleep 2
exit 0
