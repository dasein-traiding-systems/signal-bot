#!/bin/sh
export PYTHONPATH=$PYTHONPATH:./trading-core/src
echo "Export path updated $PYTHONPATH"
python signal-bot.py
