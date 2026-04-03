#!/bin/bash
cd "C:/projects/amazon-deals-bot"
PYTHONUTF8=1 $(which python3) main.py --dry-run >> "C:/projects/amazon-deals-bot/bot_dryrun.log" 2>&1
