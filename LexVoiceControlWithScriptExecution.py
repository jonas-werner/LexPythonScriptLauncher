# https://forum.omz-software.com/topic/4165/amazon-lex-using-audiorecorder/7

# from objc_util import *
import boto3
import os
import uuid
import pyaudio
import wave
import RPi.GPIO as GPIO
# import max7219
import re
import time
import argparse
from multiprocessing import Process

from luma.led_matrix.device import max7219
from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.core.virtual import viewport
from luma.core.legacy import text, show_message
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT, SINCLAIR_FONT, LCD_FONT


AWS_ACCESS_KEY_ID       = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY   = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_DEFAULT_REGION      = os.environ["AWS_DEFAULT_REGION"]

# FORMAT		= pyaudio.paInt16
# RATE 		= 16000
# CHUNK_SIZE 	= 1024
# MAX_SILENCE = 3
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 3
WAVE_OUTPUT_FILENAME = "voice.wav"

def record_request(WAVE_OUTPUT_FILENAME):

	p = pyaudio.PyAudio()

	stream = p.open(format=FORMAT,
	                channels=CHANNELS,
	                rate=RATE,
	                input=True,
	                frames_per_buffer=CHUNK)

	print("* recording")

	frames = []

	for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
	    data = stream.read(CHUNK)
	    frames.append(data)

	print("* done recording")

	stream.stop_stream()
	stream.close()
	p.terminate()

	wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
	wf.setnchannels(CHANNELS)
	wf.setsampwidth(p.get_sample_size(FORMAT))
	wf.setframerate(RATE)
	wf.writeframes(b''.join(frames))
	wf.close()

	path = os.path.abspath(WAVE_OUTPUT_FILENAME)

	return path

def play_sound(waveFile):
	os.system("mpg321 " + waveFile)


def callLex(path, user):
	recording = open(path, 'rb')
	client = boto3.client('lex-runtime',
							aws_access_key_id=AWS_ACCESS_KEY_ID,
							aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
							region_name=AWS_DEFAULT_REGION)

	r = client.post_content(botName='LightControl', botAlias='$LATEST', userId=user,
	contentType='audio/l16; rate=16000; channels=1',
	# accept='text/plain; charset=utf-8',
	accept="audio/mpeg",
	inputStream=recording)
	print(r)

	audio_stream = r['audioStream'].read()
	r['audioStream'].close()
	f = wave.open("wavefile.wav", 'wb')
	f.setnchannels(2)
	f.setsampwidth(2)
	f.setframerate(16000)
	f.setnframes(0)
	f.writeframesraw(audio_stream)
	f.close()

	return r


def lightControl(lightState):

	if lightState == "on":
		GPIO.output(17,GPIO.HIGH)
	elif lightState == "off":
		GPIO.output(17,GPIO.LOW)
	else:
		print "lightstate unknown: %s" % lightState


def showMessage(lexStatus):
    n = 4
    cascaded = 1
    block_orientation = -90
    rotate = 0
    inreverse = 0

    # create matrix device
    serial = spi(port=0, device=0, gpio=noop())
    device = max7219(serial, cascaded=n or 1, block_orientation=block_orientation,
                     rotate=rotate or 0, blocks_arranged_in_reverse_order=inreverse)
    print("Created device")

    msg = lexStatus

    msg = re.sub(" +", " ", msg)
    print(msg)
    show_message(device, msg, fill="white", font=proportional(LCD_FONT), scroll_delay=0.02)



def main():

	user = uuid.uuid4().hex

	GPIO.setmode(GPIO.BCM)
	GPIO.setwarnings(False)
	GPIO.setup(17,GPIO.OUT)

	status = ""

	while status != "Fulfilled":
		path = record_request(WAVE_OUTPUT_FILENAME)

		if path is None:
			print('Nothing recorded')
			return

		lexData = callLex(path, user)

		print "############### ORDER STATUS: %s", lexData[u'dialogState']
		status = lexData[u'dialogState']

		# showMessage(status)

		p = Process(target=showMessage, args=(status,))
		# you have to set daemon true to not have to wait for the process to join
		p.daemon = True
		p.start()
		# p.join()

		if status == "Fulfilled":
			lightState = lexData[u'slots'][u'lightState']
			lightControl(lightState)
		else:
			play_sound("wavefile.wav")


		# clean up temp files
		os.remove("wavefile.wav")
		os.remove(path)



if __name__ == '__main__':
	main()
