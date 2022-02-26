# RightClickSaveBot

A twitter bot to scrape and liberate NFT images.




### Info

Crontab:
```
SHELL=/bin/bash
BASH_ENV=~/.bashrc

0 */3 * * *   xvfb-run /home/rock/rightclick.sh >> /home/rock/logRightclick.txt  2>&1
```
