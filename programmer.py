import argparse
import serial
import sys
import xmodem
import os
import math

parser = argparse.ArgumentParser(description='Mimas V2 Programmer')
parser.add_argument('--uart', help='Path to UART device', default='/dev/ttyACM0')
parser.add_argument('--baudrate', help='Baudrate of UART device', default=115200, type=int)
parser.add_argument('--filename', help='Full path to binary file', default='build/mimasv2_base_lm32/flash.bin')
verify_parser = parser.add_mutually_exclusive_group(required=False)
verify_parser.add_argument('--verify', dest='verify', action='store_true')
verify_parser.add_argument('--no-verify', dest='verify', action='store_false')
parser.set_defaults(verify=True)
erase_parser = parser.add_mutually_exclusive_group(required=False)
erase_parser.add_argument('--erase', dest='erase', action='store_true')
erase_parser.add_argument('--no-erase', dest='erase', action='store_false')
parser.set_defaults(erase=False)
parser.add_argument('--protocol', help='XMODEM protocol (xmodem or xmodem1k)', default='xmodem1k')
args = parser.parse_args()

port = serial.Serial(args.uart, args.baudrate, timeout=0.1)

port.write(b'\x03\r\n\r\n')
port.read(100)
port.write(b'i\r')
chipid = port.read(100).decode()
chipid = chipid.split('\n')
if len(chipid) > 1 and chipid[1].strip() == '202015':
  print('Detected Mimas v2 with M25P16 SPI Flash.')
else:
  print('Didn\'t find SPI Flash.')
  sys.exit(1)

if args.erase:
  print('Erasing flash -- this takes approx 16 seconds.')
  port.write(b'e\r')
  while True:
    if port.read(1) == b'>':
      break
  port.read(1)
  print('Erase complete.')

if args.verify:
  port.write(b'C\r')
else:
  print('Warning: disabling verification.')
  port.write(b'c\r')
port.read(len('x\r\nmimas> '))

def xmodem_getc(size, timeout=1):
  port.timeout = timeout
  r = port.read(size) or None
  #print('Rx:', r)
  return r

def xmodem_putc(data, timeout=1):
  port.timeout = timeout
  #print('Tx:', data)
  return port.write(data)

# Print iterations progress
# From: https://stackoverflow.com/a/34325723/39648
def print_progress_bar(iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

print('Sending {}'.format(args.filename))
modem = xmodem.XMODEM(xmodem_getc, xmodem_putc, mode=args.protocol)
port.write(b'f\r')
port.read(3)
with open(args.filename, 'rb') as stream:
  try:
    packet_size = dict(
      xmodem    = 128,
      xmodem1k  = 1024,
    )[args.protocol]
  except KeyError:
    raise ValueError(f"Invalid mode specified: {args.protocol}")

  file_size = os.stat(args.filename).st_size
  num_packets = int(math.ceil(file_size / packet_size))
  
  def report_progress(total_packets, success_count, error_count):
    print_progress_bar(success_count, num_packets, prefix = 'Progress:', suffix = 'Complete')

  if modem.send(stream, callback=report_progress):
    print()
    print('Done.')
  else:
    print('Failed.')
