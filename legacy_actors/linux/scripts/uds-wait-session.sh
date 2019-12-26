#!/bin/sh

while :
do
  sleep 5  # Wait 5 seconds between checks
  found=`ps -f -u$PAM_USER | grep -v grep | grep -v uds-wait-session | grep "$PAM_TTY" | wc -l`
  
  if [ "$found" = "0" ]; then
    /usr/bin/udsactor logout $PAM_USER
    exit 0
  fi
done
