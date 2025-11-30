- create `.env` and fill with example
- copy service and timer into `/etc/systemd/system/`
- run,

```
sudo systemctl daemon-reload
sudo systemctl enable bottleneck.timer
sudo systemctl start bottleneck.timer
```
