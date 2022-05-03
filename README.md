# MusePaint
Python3 program to convert music to a computer-drawn image.

MUSI 4450 Final Project

Author: Colin Cassell

Created: 4/28/22

This project, MusePaint, will paint a picture on screen based on the audio input, whether
that's speaking, music, or other sound effects. It uses the tkinter library to draw, PyAudio to
take audio input, and Pillow (python imaging library) to save the images you create.

While the program is running and the canvas is selected, you can use "control-s" to save the image,
and you can use "control-c" to clear the current image.

The saved image won't perfectly match the image you see as you play, because the saved image is drawn
in a different library from the live drawing. The live drawing is with tkinter, and the saved image is drawn
with Pillow. This is the best way I could find to "save" a tkinter canvas drawing.

To install the required modules, run "pip install -r requirements.txt"

If you're on a Mac with an M1 chip, pyaudio may fail to install. You'll want to have homebrew
installed, then run "brew install portaudio" followed by "python -m pip install --global-option='build_ext' --global-option='-I/opt/homebrew/Cellar/portaudio/19.7.0/include' --global-option='-L/opt/homebrew/Cellar/portaudio/19.7.0/lib' pyaudio"
