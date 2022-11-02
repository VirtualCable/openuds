#!/usr/bin/env python3
import os
import sys
import cProfile

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")

    from django.core.management import execute_from_command_line

    cProfile.run("execute_from_command_line(sys.argv)", "/tmp/django.pyprof")
