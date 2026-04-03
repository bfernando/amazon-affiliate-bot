#!/bin/bash
cd "C:/projects/amazon-affiliate-bot"
PYTHONUTF8=1 $(which python3) main.py --dry-run >> "C:/projects/amazon-affiliate-bot/bot_dryrun.log" 2>&1
