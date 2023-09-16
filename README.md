# Pi Headless
A simple script that enables you to execute a script on a virtual Raspberry Pi to preconfigure it before flashing it onto a card

# Requirements
The Python requirements are [`paramiko`](https://www.paramiko.org) and [`pyyaml`](https://pyyaml.org/wiki/PyYAML), which are installed with:
```bash
pip install -r requirements.txt
```

It also requires having [QEMU](https://www.qemu.org/) installed

The following binaries will be used: `sudo`, `fdisk`, `mount`, `umount`, `rsync`, `qemu-system-aarch64`*, `qemu-img`, `openssl`, `wpa_passphrase`, `iw`

\* `qemu-system-aarch64` can be changed in `models.yml`, which is used to configure parameters used for QEMU to virtualize the Raspberry Pi

# Usage

You can download an image such as `*-raspios-bullseye-armhf-lite.img` or `*-raspios-bullseye-arm64-lite.img` from https://www.raspberrypi.com/software/operating-systems/

## Arguments

|Argument|Alias|Description|
|-|-|-|
|`image`||image file|
|`--model`|`-m`|model name, default `rpi-zero-2-w`|
|`--port`|`-p`|QEMU port to forward, default `5555`|
|`--no-backup`|`-n`|do not backup image|
|`--usb-mode`||`g_serial`, `g_ether`, default empty|
|`--enable-dnsmaq`||enable dnsmasq|
|`--dnsmasq-gateway`||gateway to set, default `10.20.30.1`|
|`--dnsmasq-range`||range to set, default `10.20.30.2,10.20.30.40`|
|`--dnsmasq-lease`||lease to set, default `12h`|
|`--user`||user to login, required to connect via QEMU over SSH, default; environment variable `PI_USER`|
|`--password`||password to login, required to connect via QEMU over SSH, default; environment variable `PI_PASSWORD`|
|`--rpi-os-config`||file of the first run config for Raspberry Pi OS, see [example](rpi-os-config.yml.example) file|

## Examples

Giving the image `2023-05-03-raspios-bullseye-armhf-lite.img` the following command will generate an image with `USB Gadget Ethernet`, `dnsmasq` (to provide an IP), and the following initial configuration (tested only in [Raspberry Pi OS](https://en.wikipedia.org/wiki/Raspberry_Pi_OS), the script is the one used by [Raspberry Pi Imager](https://www.raspberrypi.com/software/))

`rpi-os-cantor.yml`
```yml
user: george
password: diagonalisation
hostname: cantor
```

```bash
./pi-headless.py 2023-05-03-raspios-bullseye-armhf-lite.img --rpi-os-config rpi-os-cantor.yml --usb-mode g_ether --enable-dnsmaq
```
Since no user and password were specified, it will use the ones provided by the rpi-os-cantor.yml file

The output will be similar to:
```
Using first config
Starting qemu
Running first config
Starting qemu
Connected
Running scripts
Running /boot/scripts/dnsmasq.sh
Get:1 http://raspbian.raspberrypi.org/raspbian bullseye InRelease [15.0 kB]
Get:2 http://archive.raspberrypi.org/debian bullseye InRelease [23.6 kB]
Get:3 http://raspbian.raspberrypi.org/raspbian bullseye/main armhf Packages [13.2 MB]
Get:4 http://archive.raspberrypi.org/debian bullseye/main armhf Packages [314 kB]
Fetched 13.6 MB in 1min 13s (186 kB/s)
Reading package lists... Done
N: Repository 'http://raspbian.raspberrypi.org/raspbian bullseye InRelease' changed its 'Suite' value from 'stable' to 'oldstable'
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
apt-utils is already the newest version (2.2.4).
The following NEW packages will be installed:
  dialog
0 upgraded, 1 newly installed, 0 to remove and 33 not upgraded.
Need to get 252 kB of archives.
After this operation, 1,020 kB of additional disk space will be used.
Get:1 http://mirrors.ocf.berkeley.edu/raspbian/raspbian bullseye/main armhf dialog armhf 1.3-20201126-1 [252 kB]
Fetched 252 kB in 2s (105 kB/s)
Selecting previously unselected package dialog.
(Reading database ... 43857 files and directories currently installed.)
Preparing to unpack .../dialog_1.3-20201126-1_armhf.deb ...
Unpacking dialog (1.3-20201126-1) ...
Setting up dialog (1.3-20201126-1) ...
Processing triggers for man-db (2.9.4-2) ...
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
The following NEW packages will be installed:
  dnsmasq
0 upgraded, 1 newly installed, 0 to remove and 33 not upgraded.
Need to get 32.0 kB of archives.
After this operation, 120 kB of additional disk space will be used.
Get:1 http://mirrors.ocf.berkeley.edu/raspbian/raspbian bullseye/main armhf dnsmasq all 2.85-1 [32.0 kB]
Fetched 32.0 kB in 1s (24.9 kB/s)
Selecting previously unselected package dnsmasq.
(Reading database ... 44012 files and directories currently installed.)
Preparing to unpack .../dnsmasq_2.85-1_all.deb ...
Unpacking dnsmasq (2.85-1) ...
Setting up dnsmasq (2.85-1) ...
Created symlink /etc/systemd/system/multi-user.target.wants/dnsmasq.service → /lib/systemd/system/dnsmasq.service.
Synchronizing state of dnsmasq.service with SysV service script with /lib/systemd/systemd-sysv-install.
Executing: /lib/systemd/systemd-sysv-install enable dnsmasq
Done

```

Then once flashed and plugged into a computer, this could be accessed using the default IP `10.20.30.1`

```bash
ssh george@10.20.30.1
```
```
george@10.20.30.1's password: 
Linux cantor 6.1.21-v7+ #1642 SMP Mon Apr  3 17:20:52 BST 2023 armv7l

The programs included with the Debian GNU/Linux system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Debian GNU/Linux comes with ABSOLUTELY NO WARRANTY, to the extent
permitted by applicable law.
Last login: Fri Sep 15 05:44:34 2023 from 10.0.2.2

Wi-Fi is currently blocked by rfkill.
Use raspi-config to set the country before use.

george@cantor:~ $
```

The following command will create a Raspberry Pi image that is able to connect over serial
```bash
./pi-headless.py 2023-05-03-raspios-bullseye-armhf-lite.img --rpi-os-config rpi-os-cantor.yml --usb-mode g_serial
```
```
Using first config
Starting qemu
Running first config
Starting qemu
Connected
Running scripts
Created symlink /etc/systemd/system/getty.target.wants/getty@ttyGS0.service → /lib/systemd/system/getty@.service.
Skipping dnsmasq.sh
Done
```
Once plugged it
```bash
sudo screen /dev/ttyACM0 115200
```
```
cantor login: george
Password:
Linux cantor 6.1.21-v7+ #1642 SMP Mon Apr  3 17:20:52 BST 2023 armv7l

The programs included with the Debian GNU/Linux system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Debian GNU/Linux comes with ABSOLUTELY NO WARRANTY, to the extent
permitted by applicable law.
Last login: Sat Sep 16 03:17:43 BST 2023 on ttyGS0

Wi-Fi is currently blocked by rfkill.
Use raspi-config to set the country before use.

george@cantor:~$
```

## Scripts

The scripts will be executed in alphabetical order. All scripts will be executed from the `scripts` directory, provided they have a `.sh` extension

## Image

Due to QEMU requirements, it is necessary for the image to have a size that is a power of two; therefore, the image size will grow to the next power of 2. The size can be made smaller using the [PiShrink](https://github.com/Drewsif/PiShrink) utility