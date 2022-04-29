"""
Main file to handle listening and drawing

The settings at line 28 affect the audio input and low-level processing
The settings at line 175 affect how things get drawn based on the audio
The width and height of the drawing canvas are located at line 329
"""

import copy
from tkinter.filedialog import asksaveasfile
from pyaudio import PyAudio, paInt16
from threading import Thread
import numpy as np
import sys
import collections

from tkinter import *
import random as rand

import colorsys
from PIL import Image, ImageDraw
from enum import Enum



class AudioAnalyzer(Thread):
    # settings: (are tuned for best detecting string instruments like guitar)
    SAMPLING_RATE = 44100  # mac hardware: 44100, 48000, 96000
    CHUNK_SIZE = 1024  # number of samples
    BUFFER_TIMES = 50  # buffer length = CHUNK_SIZE * BUFFER_TIMES
    ZERO_PADDING = 3  # times the buffer length
    NUM_HPS = 3  # Harmonic Product Spectrum

    maxValue = 2**16



    # overall frequency accuracy (step-size):  SAMPLING_RATE / (CHUNK_SIZE * BUFFER_TIMES * (1 + ZERO_PADDING)) Hz
    #               buffer length in seconds:  (CHUNK_SIZE * BUFFER_TIMES) / SAMPLING_RATE sec

    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    COLOR =      ["red", "red", "yellow", "yellow", "yellow", "green", "green", "cyan", "cyan", "blue", "blue", "magenta"]
    color_map = {key: item for key, item in zip(NOTE_NAMES, COLOR)}

    def __init__(self, queue, *args, **kwargs):
        Thread.__init__(self, *args, **kwargs)

        self.queue = queue  # queue should be instance of ProtectedList (threading_helper.ProtectedList)
        self.buffer = np.zeros(self.CHUNK_SIZE * self.BUFFER_TIMES)
        self.hanning_window = np.hanning(len(self.buffer))
        self.running = False

        try:
            self.audio_object = PyAudio()
            self.stream = self.audio_object.open(format=paInt16,
                                                 channels=1,
                                                 rate=self.SAMPLING_RATE,
                                                 input=True,
                                                 output=False,
                                                 frames_per_buffer=self.CHUNK_SIZE)
        except Exception as e:
            sys.stderr.write('Error: Line {} {} {}\n'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
            return

    @staticmethod
    def frequency_to_number(freq, a4_freq):
        """ converts a frequency to a note number (for example: A4 is 69)"""

        if freq == 0:
            sys.stderr.write("Error: No frequency data. Program has potentially no access to microphone\n")
            return 0

        return 12 * np.log2(freq / a4_freq) + 69

    @staticmethod
    def number_to_frequency(number, a4_freq):
        """ converts a note number (A4 is 69) back to a frequency """

        return a4_freq * 2.0**((number - 69) / 12.0)

    @staticmethod
    def number_to_note_name(number):
        """ converts a note number to a note name (for example: 69 returns 'A', 70 returns 'A#', ... ) """

        return AudioAnalyzer.NOTE_NAMES[int(round(number) % 12)]

    @staticmethod
    def frequency_to_note_name(frequency, a4_freq):
        """ converts frequency to note name (for example: 440 returns 'A') """

        number = AudioAnalyzer.frequency_to_number(frequency, a4_freq)
        note_name = AudioAnalyzer.number_to_note_name(number)
        return note_name


    def run(self):
        """ Main function where the microphone buffer gets read and
            the audio data handled and analyzed """

        self.running = True


        while self.running:
            try:
                # read microphone data
                data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                data = np.frombuffer(data, dtype=np.int16)

                # VOLUME CALCULATIONS
                dataL = data[0::2]
                dataR = data[1::2]
                peakL = np.abs(np.max(dataL)-np.min(dataL))/self.maxValue
                peakR = np.abs(np.max(dataR)-np.min(dataR))/self.maxValue

                thisVolAvg = (peakL + peakR) / 2

                # FREQUENCY CALCULATIONS

                # append data to audio buffer
                self.buffer[:-self.CHUNK_SIZE] = self.buffer[self.CHUNK_SIZE:]
                self.buffer[-self.CHUNK_SIZE:] = data

                # apply the fourier transformation on the whole buffer (with zero-padding + hanning window)
                magnitude_data = abs(np.fft.fft(np.pad(self.buffer * self.hanning_window,
                                                       (0, len(self.buffer) * self.ZERO_PADDING),
                                                       "constant")))
                # only use the first half of the fft output data
                magnitude_data = magnitude_data[:int(len(magnitude_data) / 2)]

                # HPS: multiply data by itself with different scalings (Harmonic Product Spectrum)
                magnitude_data_orig = copy.deepcopy(magnitude_data)
                for i in range(2, self.NUM_HPS+1, 1):
                    hps_len = int(np.ceil(len(magnitude_data) / i))
                    magnitude_data[:hps_len] *= magnitude_data_orig[::i]  # multiply every i element

                # get the corresponding frequency array
                frequencies = np.fft.fftfreq(int((len(magnitude_data) * 2) / 1),
                                             1. / self.SAMPLING_RATE)

                # set magnitude of all frequencies below 60Hz to zero
                for i, freq in enumerate(frequencies):
                    if freq > 60:
                        magnitude_data[:i - 1] = 0
                        break

                # put the frequency of the loudest tone and its volume into the queue
                self.queue.put((round(frequencies[np.argmax(magnitude_data)], 2), thisVolAvg))

            except Exception as e:
                sys.stderr.write('Error: Line {} {} {}\n'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))

        self.stream.stop_stream()
        self.stream.close()
        self.audio_object.terminate()


def getRandX():
    return rand.randint(20, width - 20)

def getRandY():
    return rand.randint(20, height - 20)


class UpdateDrawing(Thread):
    isDrawing = False

    # holds the last 15 volumes
    movingVols = collections.deque(maxlen=15)
    lastPoint = (0, 0)

    # holds the shapes that can be drawn
    shapes = Enum('Shape', 'rectangle oval')


    # tuning parameters
    initial_width = 10

    # d represents the distance between consecutive shapes that are drawn
    # a value of around 10 is recommended, but d = 100 produces fun effects as well
    initial_d = 10

    initial_shape = shapes.rectangle

    # volume parameters (volume is represented as a decimal between 0 and 1)
    # if current volume is above this value, it will begin drawing if not already
    start_thresh = .1

    # if the average of the past 15 volumes is below this value, the program will stop drawing if currently drawing
    end_thresh = .0075

    # if the difference between the current volume and the last volume is greater than this, then the drawing will
    # increase/decrease in width/height, depending on if the volume increased by the threshold or decreased by the threshold
    vol_thresh = .0035

    # if any 2 of the last 15 volumes had a difference greater than this value, then the shape will be
    # a rectangle rather than an oval
    shape_thresh = .1
    
    # boolean parameter to enable or disable the d value changing throughout the program based on volume (I prefer it off)
    d_variation = False

    # boolean parameter that would make rectangle the only shape used
    force_rectangle = False

    # color parameters in hsv (hue is mapped to pitch at line 269)
    saturation = .85
    value = .9

    width = initial_width
    shape = initial_shape
    d = initial_d

    def __init__(self, wn, draw, win_width, win_height, *args, **kwargs):
        Thread.__init__(self, *args, **kwargs)
        self.q = ProtectedList()
        self.a = AudioAnalyzer(self.q)
        self.a.start()
        self.wn = wn
        self.draw = draw
        self.win_width = win_width
        self.win_height = win_height

    
    def create_line(self, x, y, x1, y1, fill, width):
        dx = x1 - x
        dy = y1 - y
        x %= self.win_width
        y %= self.win_height
        x1 = x + dx
        y1 = y + dy
            
        if self.shape == self.shapes.rectangle or self.force_rectangle:
            self.wn.create_line(x, y, x1, y1, fill=fill, width=width)
            self.draw.line([(int(x), int(y)), (int(x1), int(y1))], fill=fill, width=int(width))
        else:
            self.wn.create_oval(x, y, x1 + width, y1, fill=fill)

    def run(self):
        while True:
            q_data = self.q.get()
            if q_data is not None:
                frequency, volume = q_data
                note = self.a.frequency_to_note_name(frequency, 440)
                print("loudest frequency:", frequency, "nearest note:", note, "at volume:", volume)         
                

                if len(self.movingVols) != 0:
                    movingAvg = sum(self.movingVols) / len(self.movingVols)

                    # volume differential between current and previous volume
                    volume_d = volume - self.movingVols[-1]

                freq_num = self.a.frequency_to_number(frequency, 440)
                hue = (freq_num % 12) / 12.0
                r, g, b = colorsys.hsv_to_rgb(hue, self.saturation, self.value)
                color = ('#{:X}{:X}{:X}').format(round(r * 255), round(g * 255), round(b * 255))

                if self.isDrawing:
                    if movingAvg < self.end_thresh:
                        # end line
                        self.isDrawing = False
                        self.d = self.initial_d
                    elif volume_d > self.vol_thresh:

                        if self.d_variation:
                            # fun addition:
                            if self.d > 100:
                                self.d -= 1
                            elif self.d < 8:
                                self.d = 8
                            elif volume_d > .09:
                                self.d += 5
                            elif movingAvg < self.end_thresh + .01:
                                self.d -= 3

                        vols = list(self.movingVols)
                        greatest_diff = max(abs(x - y) for x, y in zip(vols, vols[1:]))

                        if greatest_diff > self.shape_thresh:
                            self.shape = self.shapes.rectangle
                        else:
                            self.shape = self.shapes.oval
                        
                        # width increase
                        self.width = (self.width + 1 if self.width < 55 else self.width)
                        x, y = self.lastPoint
                        self.create_line(x, y, x + self.d, y - self.d, fill=color, width=self.width)
                        self.lastPoint = (x + self.d, y - self.d)
                    elif volume_d < -self.vol_thresh:
                        # width decrease
                        self.width = (self.width - 1 if self.width > 1 else self.width)
                        x, y = self.lastPoint
                        self.create_line(x, y, x + self.d, y + self.d, fill=color, width=self.width)
                        self.lastPoint = (x + self.d, y + self.d)
                    else:
                        x, y = self.lastPoint
                        self.create_line(x, y, x + self.d, y, fill=color, width=self.width)
                        self.lastPoint = (x + self.d, y)

                elif volume > self.start_thresh:
                    self.width = 160 * volume
                    x = getRandX()
                    y = getRandY()
                    self.create_line(x, y, x + self.d, y, fill=color, width=self.width)
                    self.lastPoint = (x + self.d, y)
                    self.isDrawing = True

                self.movingVols.append(volume)

                time.sleep(0.02)

def save_pic(image):
    files = [('PNG Files', '*.png')]
    file = asksaveasfile(filetypes = files, defaultextension = files)
    image.save(file.name)

def clear_images(canvas, draw, width, height):
    canvas.delete('all')
    draw.rectangle((0, 0, width, height), fill = (255, 255, 255, 100))


if __name__ == "__main__":
    from threading_helper import ProtectedList
    import time

    root = Tk()
    root.title("Paint Application")

    # width and height of canvas
    width = 1320
    height = 750

    root.geometry("" + str(width) + "x" + str(height))

    wn=Canvas(root, width=width, height=height, bg='white')

    invisibleImage = Image.new("RGB", (width, height), tuple([255]*3))
    draw = ImageDraw.Draw(invisibleImage)

    root.bind('<Control-s>', lambda _: save_pic(invisibleImage))
    root.bind('<Control-c>', lambda _: clear_images(wn, draw, width, height))

    u = UpdateDrawing(wn, draw, width, height)
    u.start()

    wn.pack()
    root.mainloop()

 