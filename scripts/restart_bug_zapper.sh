sudo systemctl daemon-reload
sudo systemctl stop bug_zapper.service
sudo systemctl start bug_zapper.service
sudo journalctl -u bug_zapper.service -f
