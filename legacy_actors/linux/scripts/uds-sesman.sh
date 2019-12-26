#!/bin/sh

env > /tmp/env.txt

if [ "$PAM_TYPE" = "open_session" ]; then
  nohup /usr/bin/udsactor login $PAM_USER &
  # Wait in backgroud to TTY to close (close_session is not being invoked right now)
  nohup /usr/bin/uds-wait-session &
elif [ "$PAM_TYPE" = "close_session" ]; then
  nohup /usr/bin/udsactor logout $PAM_USER &
fi

return 0
