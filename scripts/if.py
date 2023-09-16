#!/usr/bin/env python
from pathlib import Path
import re
import argparse

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("-i", help="path to interfaces file", default="/etc/network/interfaces", type=Path)
  parser.add_argument("-a", help="address to set", default="10.77.77.77")
  parser.add_argument("-m", help="netmask to set", default="255.255.255.0")
  args = parser.parse_args()

  with args.i.open() as f:
    data = f.read()

  template = lambda a, m: f"""
auto usb0
allow-hotplug usb0
iface usb0 inet static
address {a}
netmask {m}
"""
  p = re.compile(template(*[r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"] * 2))
  if p.search(data):
    m = p.sub(template(args.a, args.m), data)
  else:
    m = data + template(args.a, args.m)
  with args.i.open("w") as f:
    f.write(m)

if __name__ == "__main__":
  main()
