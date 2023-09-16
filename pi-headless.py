#!/usr/bin/env python
import subprocess
from pathlib import Path
import re
from threading import Thread
import paramiko
import time
import os
import math
import yaml
import argparse

paramiko.util.log_to_file(os.devnull, level = "INFO")

def exec(cmd):
  return subprocess.check_output(list(map(str, cmd)), text=True).strip()

class FirstConfig:
  def __init__(self, yaml_file):
    self.yaml_file = yaml_file
    self.hostname = None
    self.user = None
    self.password_hash = None
    self.wifi_name = None
    self.wifi_psk = None
    self.wifi_country = None
    self.keyboard_layout = None
    self.timezone = None
    self.parse()

  def parse(self):
    with open(self.yaml_file) as f:
      self.data = yaml.safe_load(f)
    self.hostname = self.data.get("hostname")
    self.user = self.data.get("user")
    self.password_hash = self.data.get("password-hash")
    self.password = self.data.get("password")
    if self.password and not self.password_hash:
      self.password_hash = exec(["openssl", "passwd", "-6", self.password])
    self.enable_ssh = self.data.get("enable-ssh", True)
    self.wifi_name = self.data.get("wifi", {}).get("name")
    self.wifi_psk = self.data.get("wifi", {}).get("psk")
    self.wifi_password = self.data.get("wifi", {}).get("password")
    if self.wifi_name and self.wifi_password and not self.wifi_psk:
      self.wifi_psk = exec(["wpa_passphrase", self.wifi_name, self.wifi_password])
      self.wifi_psk = self.wifi_psk.split("psk=")[-1].split("\n")[0]
    self.wifi_country = self.data.get("wifi", {}).get("country")
    if self.wifi_name and self.wifi_psk and not self.wifi_country:
      try:
        self.wifi_country = exec(["iw", "reg", "get"]).split("country ")
        self.wifi_country = re.split(r"[\s\n:]", self.wifi_country[-1])[0]
      except:
        self.wifi_country = "GB"
    self.keyboard_layout = self.data.get("keyboard-layout")
    self.timezone = self.data.get("timezone")

  def get_script(self):
    script = "#!/bin/bash\n\nset +e\n\n"
    if self.hostname:
      script += f"""
CURRENT_HOSTNAME=`cat /etc/hostname | tr -d " \\t\\n\\r"`
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_hostname {self.hostname}
else
   echo {self.hostname} >/etc/hostname
   sed -i "s/127.0.1.1.*$CURRENT_HOSTNAME/127.0.1.1\t{self.hostname}/g" /etc/hosts
fi\n
"""
    if self.enable_ssh:
      script += f"""
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom enable_ssh
else
   systemctl enable ssh
fi\n
"""
    if self.user and self.password_hash:
      script += f"""
FIRSTUSER=`getent passwd 1000 | cut -d: -f1`
FIRSTUSERHOME=`getent passwd 1000 | cut -d: -f6`
if [ -f /usr/lib/userconf-pi/userconf ]; then
   /usr/lib/userconf-pi/userconf '{self.user}' '{self.password_hash}'
else
   echo "$FIRSTUSER:"'{self.password_hash}' | chpasswd -e
   if [ "$FIRSTUSER" != "{self.user}" ]; then
      usermod -l "{self.user}" "$FIRSTUSER"
      usermod -m -d "/home/{self.user}" "{self.user}"
      groupmod -n "{self.user}" "$FIRSTUSER"
      if grep -q "^autologin-user=" /etc/lightdm/lightdm.conf ; then
         sed /etc/lightdm/lightdm.conf -i -e "s/^autologin-user=.*/autologin-user={self.user}/"
      fi
      if [ -f /etc/systemd/system/getty@tty1.service.d/autologin.conf ]; then
         sed /etc/systemd/system/getty@tty1.service.d/autologin.conf -i -e "s/$FIRSTUSER/{self.user}/"
      fi
      if [ -f /etc/sudoers.d/010_pi-nopasswd ]; then
         sed -i "s/^$FIRSTUSER /{self.user} /" /etc/sudoers.d/010_pi-nopasswd
      fi
   fi
fi\n
"""

    if self.wifi_name and self.wifi_psk:
      script += f"""
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_wlan '{self.wifi_name}' '{self.wifi_psk}' '{self.wifi_country}'
else
cat >/etc/wpa_supplicant/wpa_supplicant.conf <<'WPAEOF'
country={self.wifi_country}
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
ap_scan=1

update_config=1
network={{
	ssid="{self.wifi_name}"
	psk={self.wifi_psk}
}}

WPAEOF
   chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf
   rfkill unblock wifi
   for filename in /var/lib/systemd/rfkill/*:wlan ; do
       echo 0 > $filename
   done
fi\n
"""
    if self.keyboard_layout:
      script += f"""
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_keymap '{self.keyboard_layout}'
else
cat >/etc/default/keyboard <<'KBEOF'
XKBMODEL="pc105"
XKBLAYOUT="{self.keyboard_layout}"
XKBVARIANT=""
XKBOPTIONS=""

KBEOF
   dpkg-reconfigure -f noninteractive keyboard-configuration
fi\n
"""
    if self.timezone:
      script += f"""
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_timezone '{self.timezone}'
else
   rm -f /etc/localtime
   echo "{self.timezone}" >/etc/timezone
   dpkg-reconfigure -f noninteractive tzdata
fi\n
"""
    script += f"""
rm -f /boot/firstrun.sh
sed -i 's| systemd.run.*||g' /boot/cmdline.txt
exit 0
"""
    return script

class Mounter:
  def __init__(self, image, target_dir = "boot", partition_index = 0):
    self.image = image
    self.target_dir = target_dir
    self.partition_index = partition_index
    self.start = self.get_offset()

  def get_offset(self):
    cmd_output = subprocess.check_output(['fdisk', '-l', self.image], text=True)
    lines = cmd_output.splitlines()
    if len(lines) < 3:
      print("fdisk output is too short")
      exit(1)
    
    header = None
    sector_size = None
    start_offset = None
    index = 0
    for line in lines[1:]:
      if line.startswith("Sector size"):
        sector_size = int(line.split(":")[1].strip().split()[0])
      if line.startswith("Device"):
        header = line
        index = 0
        continue
      if header:
        if index == self.partition_index:
          boot, start = header.find("Boot"), header.find("Start")
          if boot == -1 or start == -1:
            print("fdisk output is not as expected")
            exit(1)
          start_offset = int(line[boot + 4:start + 5].strip())
          break
        index += 1
    return sector_size * start_offset
  
  def mount(self):
    Path(self.target_dir).mkdir(exist_ok=True)
    subprocess.run(['sudo', 'mount', '-o', f'loop,offset={self.start}', self.image, self.target_dir])

  def umount(self):
    subprocess.run(['sudo', 'umount', self.target_dir])
    Path(self.target_dir).rmdir()

class QemuPreparer:
  def __init__(self, source_dir, usb_mode, model, first_config, target_dir = "data"):
    self.source_dir = source_dir
    self.target_dir = target_dir
    self.usb_mode = usb_mode
    self.model = model
    self.target_string = model["dtb-target-string"]
    self.target_kernel = model["kernel-match-string"]
    self.first_config = first_config

  def get_dtb(self, ):
    for i in Path(self.source_dir).glob("*.dtb"):
      if i.name.find(self.target_string) != -1:
        self.current_dtb = i
        return i
    
  def get_kernel(self):
    files = []
    for i in Path(self.source_dir).glob("*.img"):
      if re.match(self.target_kernel, i.name):
        size = i.stat().st_size
        files.append((i, size))
    files.sort(key=lambda x: x[1])
    self.current_kernel = files[-1][0]
    return files[-1][0]
  
  def get_target_dtb(self):
    return Path(self.target_dir, self.current_dtb.name)
  
  def get_target_kernel(self):
    return Path(self.target_dir, self.current_kernel.name)
  
  def copy_files(self):
    Path(self.target_dir).mkdir(exist_ok=True)
    dtb = self.get_dtb()
    kernel = self.get_kernel()
    subprocess.run(['cp', dtb, kernel, self.target_dir])
    subprocess.run(['sudo', 'rsync', '-a', '--no-o', '--no-g', "scripts/", Path(self.source_dir, "scripts/")])

  def set_usb_mode(self):
    if not self.usb_mode:
      return
    config_txt = Path(self.source_dir, "config.txt")
    target = "\ndtoverlay=dwc2"
    with config_txt.open() as f:
      data = f.read()
    if data.find(target) == -1:
      data += target + "\n"
    subprocess.run(["sudo", "tee", config_txt], input=data.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cmdline_txt = Path(self.source_dir, "cmdline.txt")
    with cmdline_txt.open() as f:
      data = f.read()
    target = r"modules-load=dwc2,\w+"

    if not re.search(target, data):
      data = data.replace("rootwait", f"rootwait modules-load=dwc2,{self.usb_mode}")
    else:
      data = re.sub(target, f"modules-load=dwc2,{self.usb_mode}", data)
    subprocess.run(["sudo", "tee", cmdline_txt], input=data.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

  def set_first_config(self):
    if not self.first_config:
      return
    firstrun_sh = Path(self.source_dir, "firstrun.sh")
    script = self.first_config.get_script()
    subprocess.run(["sudo", "tee", firstrun_sh], input=script.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["sudo", "chmod", "+x", firstrun_sh])

  def prepare(self):
    self.copy_files()
    self.set_usb_mode()
    self.set_first_config()

class QemuRunner:
  def __init__(self, qemu_preparer, image, user, password, port, dnsmasq):
    self.image = image
    self.qp = qemu_preparer
    self.port = port
    self.user = user
    self.password = password
    self.first_config = qemu_preparer.first_config
    self.model = qemu_preparer.model
    self.dnsmasq = dnsmasq
    self.usb_mode = qemu_preparer.usb_mode

  def get_commands(self, first_config = False):
    first_config_extra = ""
    if first_config:
      first_config_extra = " systemd.run=/boot/firstrun.sh systemd.run_success_action=reboot systemd.run_failure_action=poweroff"
    return [
      self.model["qemu"]["bin"],
      "-machine",
      self.model["qemu"]["machine"],
      "-cpu",
      self.model["qemu"]["cpu"],
      "-m",
      self.model["qemu"]["memory"],
      "-nographic",
      "-dtb",
      self.qp.get_target_dtb(),
      "-kernel",
      self.qp.get_target_kernel(),
      "-append",
      f"console=ttyAMA0 root=/dev/mmcblk0p2 rw rootwait rootfstype=ext4{first_config_extra}",
      "-no-reboot",
      "-device",
      "usb-net,netdev=net0",
      "-netdev",
      f"user,id=net0,hostfwd=tcp::{self.port}-:22",
      "-drive",
      f'format=raw,file={self.image}'
    ]

  def enlarge_image(self):
    size = Path(self.image).stat().st_size
    size = 2**(math.ceil(math.log(size, 2)))
    subprocess.run(['qemu-img', 'resize', self.image, str(size)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

  def run(self):
    if self.first_config:
      print("Starting qemu")
      print("Running first config")
      subprocess.run(self.get_commands(True), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def qemu():
      subprocess.run(self.get_commands(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Starting qemu")
    Thread(target=qemu).start()
    self.wait()

  def exec(self, client, cmd, env = {}, hide = False):
    e = client.exec_command(cmd, get_pty=True, environment=env)
    t = [e[i].read().decode("utf-8").strip() for i in [1, 2]]
    if not hide:
      for i in t:
        if len(i) > 0:
          print(i)
    [i.close() for i in e]
    return t

  def wait(self):
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.get_host_keys().clear()
    while True:
      try:
        client.connect("localhost", username=self.user, password=self.password, port=self.port)
        print("Connected")
        time.sleep(1)
        print("Running scripts")
        if self.usb_mode == "g_serial":
          self.exec(client, "sudo systemctl enable getty@ttyGS0.service")
        output, _ = self.exec(client, "/bin/ls -1p /boot/scripts/*.sh", hide=True)
        scripts = []
        for i in output.split("\n"):
          i = i.strip()
          if not self.dnsmasq:
            if i.endswith("/dnsmasq.sh"):
              print("Skipping dnsmasq.sh")
              continue
          if len(i) > 0:
            scripts.append(i)
        for i in sorted(scripts):
          print(f"Running {i}")
          if i.endswith("/dnsmasq.sh"):
            self.exec(client, f"sudo /bin/bash {i} {self.dnsmasq.dnsmasq_gateway} {self.dnsmasq.dnsmasq_range} {self.dnsmasq.dnsmasq_lease}")
          else:
            self.exec(client, f"sudo /bin/bash {i}")
        print("Done")
        time.sleep(1)
        self.exec(client, "sudo shutdown now")
        time.sleep(1)
        break
      except:
        time.sleep(10)
  
class Dnsmasq:
  def __init__(self, dnsmasq_gateway, dnsmasq_lease, dnsmasq_range):
    self.dnsmasq_gateway = dnsmasq_gateway
    self.dnsmasq_lease = dnsmasq_lease
    self.dnsmasq_range = dnsmasq_range

def main():
  with open("models.yml") as m:
    models = yaml.safe_load(m)
  parser = argparse.ArgumentParser()
  parser.add_argument("image", help="image file")
  parser.add_argument("-m", "--model", help="model name", choices=models.keys(), default="rpi-zero-2-w")
  parser.add_argument("-p", "--port", help="QEMU port to forward", default=5555, type=int)
  parser.add_argument("-n", "--no-backup", help="do not backup image", action="store_true")
  parser.add_argument("--usb-mode", help="USB mode", choices=["g_serial", "g_ether", ""], default="")
  parser.add_argument("--enable-dnsmaq", help="enable dnsmasq", action="store_true")
  parser.add_argument("--dnsmasq-gateway", help="gateway to set", default="10.20.30.1")
  parser.add_argument("--dnsmasq-range", help="range to set", default="10.20.30.2,10.20.30.40")
  parser.add_argument("--dnsmasq-lease", help="lease to set", default="12h")
  parser.add_argument("--user", help="user to login, read from env PI_USER if not set")
  parser.add_argument("--password", help="password to login, read from env PI_PASSWORD if not set")
  parser.add_argument("--rpi-os-config", help="file of the first run config for Raspberry Pi OS, see example file")

  args = parser.parse_args()

  user = os.environ.get("PI_USER", args.user)
  password = os.environ.get("PI_PASSWORD", args.password)

  first_config = None
  if args.rpi_os_config:
    first_config = FirstConfig(args.rpi_os_config)
    if not user:
      user = first_config.user
    if not password:
      password = first_config.password
    print("Using first config")
  if not user or not password:
    print("User and password are not set")
    exit(1)

  dnsmasq = None
  if args.enable_dnsmaq:
    dnsmasq = Dnsmasq(args.dnsmasq_gateway, args.dnsmasq_lease, args.dnsmasq_range)

  model = models[args.model]

  if not args.no_backup:
    exec(["cp", args.image, args.image + ".bak"])

  m = Mounter(args.image)
  qp = QemuPreparer(m.target_dir, args.usb_mode, model, first_config)
  m.mount()
  qp.prepare()
  m.umount()
  qr = QemuRunner(qp, m.image, user, password, args.port, dnsmasq)
  qr.enlarge_image()
  qr.run()


if __name__ == "__main__":
  main()
