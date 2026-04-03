#!/bin/bash
cd "C:/projects/amazon-affiliate-bot"
PYTHONUTF8=1 $(which python3) main.py --post --mode best >> "C:/projects/amazon-affiliate-bot/bot.log" 2>&1
