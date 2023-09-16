#!/usr/bin/env python
from pathlib import Path
import re
import argparse

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("-d", help="path to dnsmasq config file", default="/etc/dnsmasq.conf", type=Path)
  parser.add_argument("-r", help="range to set", default="10.77.77.78,10.77.77.99")
  parser.add_argument("-l", help="lease to set", default="12h")
  args = parser.parse_args()

  with args.d.open() as f:
    data = f.read()

  template = lambda r, l: f"""
dhcp-range={r},{l}
dhcp-option=3
dhcp-option=6
"""
  p = re.compile(template(",".join([r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"] * 2), r"\d{1,2}[hms]"))
  if p.search(data):
    m = p.sub(template(args.r, args.l), data)
  else:
    m = data + template(args.r, args.l)
  with args.d.open("w") as f:
    f.write(m)

if __name__ == "__main__":
  main()
