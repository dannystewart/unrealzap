# Unreal Zap

Based on an amazing idea to have the Unreal Tournament kill streak sounds play when the bug zapper goes off, this script makes that dream a reality.

It listens to microphone input and waits for a burst of sound over a certain volume threshold, then plays the appropriate Unreal Tournament kill streak sound based on number of kills so far that day.

It also supports multi-kills—if you get multiple zaps within 60 seconds, you'll be treated to "double kill" instead of "killing spree," and so on. If you get more zaps than there are sounds, you're treated to "Headshot!" for the rest of that day.

The script resets at midnight each day, and supports quiet hours to avoid going off overnight.

## Sounds

In addition to "Headshot," the following sounds are included:

### Kill Streak

1. First Blood
2. Killing Spree
3. Rampage
4. Dominating
5. Unstoppable
6. Godlike

### Multi-Kills

1. Double Kill
2. Multi-Kill
3. Ultra Kill
4. Monster Kill

## Setting Up a Raspberry Pi

This is simple to set up with a Raspberry Pi and a USB conference mic that works with Linux like [this one](https://www.amazon.com/dp/B0899S421T).

Make sure the Raspberry Pi is up-to-date:

```bash
sudo apt update
sudo apt upgrade
```

Install using pip:

```bash
pip install unrealzap
```

Create a `systemd` service to run the script on startup:

```bash
sudo nano /etc/systemd/system/unrealzap.service
```

Configure like so:

```bash
[Unit]
Description=Unreal Zap
After=network.target sound.target
Wants=sound.target

[Service]
ExecStart=/path/to/python -m unrealzap.bug_zapper:main
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=5
User=danny
Group=audio
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin  # May need adjustment
Environment=PYTHONUNBUFFERED=1
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=ALSA_CARD=S3
TimeoutStopSec=10
Nice=-10

[Install]
WantedBy=multi-user.target
```

Enable and start the service, and check the status to confirm:

```bash
sudo systemctl enable --now unrealzap.service
sudo systemctl start unrealzap.service
sudo systemctl status unrealzap.service
```

M-M-M-M-MONSTER KILL!
