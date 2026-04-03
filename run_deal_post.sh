#!/bin/bash
# Amazon Deals Bot - Automated deal posting
# Keep cron behavior aligned with the main app path.

cd "C:/projects/amazon-deals-bot"

echo "$(date): Running main.py --post --mode best"
PYTHONUTF8=1 python3 main.py --post --mode best
