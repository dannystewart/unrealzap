# Bug Zapper Kill Streak Tracker

Based on Ian's amazing idea to have the Unreal Tournament kill streak sounds play when the bug zapper goes off, this script makes that dream a reality.

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

This is simple to set up with a Raspberry Pi and a cheap-ish USB conference mic that works with Linux like [this one](https://www.amazon.com/Bluetooth-Speakerphone-Microphone-Reduction-Algorithm/dp/B08DNTXYCT).

Make sure the Raspberry Pi is up-to-date:

```bash
sudo apt-get update
sudo apt-get upgrade
```

Install Poetry:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Add Poetry to your PATH (if not done automatically):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Clone the project and set up the virtual environment:

```bash
cd /path/to/your/project
poetry install --no-root
```
Create a `systemd` service to run the script on startup:

```bash
sudo nano /etc/systemd/system/bug_zapper.service
```

Configure like so:

```
[Unit]
Description=Bug Zapper Kill Streak Tracker
After=network.target

[Service]
ExecStart=/home/pi/.local/bin/poetry run python /path/to/your/project/bug_zapper.py
WorkingDirectory=/path/to/your/project
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start the service, and check the status to confirm:

```bash
sudo systemctl enable --now bug_zapper.service
sudo systemctl start bug_zapper.service
sudo systemctl status bug_zapper.service
```

M-M-M-M-MONSTER KILL!
