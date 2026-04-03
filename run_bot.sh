#!/bin/bash
cd "C:/projects/amazon-deals-bot"
PYTHONUTF8=1 $(which python3) main.py --post --mode best >> "C:/projects/amazon-deals-bot/bot.log" 2>&1
