#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests the audacity pipe.

Keep pipe_test.py short!!
You can make more complicated longer tests to test other functionality
or to generate screenshots etc in other scripts.

Make sure Audacity is running first and that mod-script-pipe is enabled
before running this script.

Requires Python 2.7 or later. Python 3 is strongly recommended.

"""

import os
import sys
import time

if sys.platform == 'win32':
    print("pipe-test.py, running on windows")
    TONAME = '\\\\.\\pipe\\ToSrvPipe'
    FROMNAME = '\\\\.\\pipe\\FromSrvPipe'
    EOL = '\r\n\0'
else:
    print("pipe-test.py, running on linux or mac")
    TONAME = '/tmp/audacity_script_pipe.to.' + str(os.getuid())
    FROMNAME = '/tmp/audacity_script_pipe.from.' + str(os.getuid())
    EOL = '\n'

print("Write to  \"" + TONAME +"\"")
if not os.path.exists(TONAME):
    print(" ..does not exist.  Ensure Audacity is running with mod-script-pipe.")
    sys.exit()

print("Read from \"" + FROMNAME +"\"")
if not os.path.exists(FROMNAME):
    print(" ..does not exist.  Ensure Audacity is running with mod-script-pipe.")
    sys.exit()

print("-- Both pipes exist.  Good.")

TOFILE = open(TONAME, 'w')
print("-- File to write to has been opened")
FROMFILE = open(FROMNAME, 'rt')
print("-- File to read from has now been opened too\r\n")


def send_command(command):
    """Send a single command."""
    print("Send: >>> \n"+command)
    TOFILE.write(command + EOL)
    TOFILE.flush()

def get_response():
    """Return the command response."""
    result = ''
    line = ''
    while True:
        result += line
        line = FROMFILE.readline()
        if line == '\n' and len(result) > 0:
            break
    return result


def do_command(command):
    """Send one command, and return the response."""
    send_command(command)
    response = get_response()
    print("Rcvd: <<< \n" + response)
    return response

# Up until here the code is unchanged from the macro test pipe available on the audacity github
# Update these to match your local directories
in_dir = "/path/to/input/audio"
out_dir = "/path/to/output/audio"

filenames = [f for f in os.listdir(in_dir) if f.lower().endswith("wav")]



def apply_macro(filenames, in_dir, out_dir):
    # This prevents Audacity from accumulating undo state across files,
    # which is the primary cause of slowdown on subsequent files.
    do_command("SetPreference: Name=GUI/MaxUndoLevels Value=0 Reload=0")

    for f in filenames:
        input_path = os.path.abspath(os.path.join(in_dir, f))
        output_path = os.path.abspath(os.path.join(out_dir, f))

        print(f"\n--- Processing: {f} ---")

        do_command(f'Import2: Filename="{input_path}"')
        do_command("SelectAll:")
        # if you create another macro/rename it, make sure to update the name after the underscore
        do_command("Macro_Denoiseok:")
        do_command(f'Export2: Filename="{output_path}" NumChannels=1')

        # Close the track 
        do_command("SelectAll:")
        do_command("RemoveTracks:")  

        # small sleep for Audacity to settle time.
       
        time.sleep(0.1)

    # Restore undo history to default (10 levels) after batch is done
    do_command("SetPreference: Name=GUI/MaxUndoLevels Value=10 Reload=0")
        

apply_macro(filenames, in_dir, out_dir)
