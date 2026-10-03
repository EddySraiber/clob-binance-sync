#!/usr/bin/env bash
# Usage: ./run.sh <command>
#
#   setup   - create venv + install deps
#   test    - run unit tests (order book + gap/resync logic)
#   demo    - print order book before/after an update (no network)
#   live    - connect to real Binance feed and keep book live-synced (needs network)
#   docker  - build Docker image (runs tests during build)
#   dtest   - run tests inside Docker
#   ddemo   - run demo inside Docker (no network)
#   dlive   - run live against Binance inside Docker (needs network)
set -e

case "$1" in
  setup)
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ;;
  test)
    source .venv/bin/activate
    pytest tests/ -v
    ;;
  demo)
    source .venv/bin/activate
    python demo.py
    ;;
  live)
    source .venv/bin/activate
    python main.py "${2:-btcusdt}"
    ;;
  docker)
    docker build -t clob .
    ;;
  dtest)
    docker run --rm clob pytest tests/ -v
    ;;
  ddemo)
    docker run --rm clob
    ;;
  dlive)
    docker run --rm clob python main.py "${2:-btcusdt}"
    ;;
  *)
    echo "Usage: ./run.sh {setup|test|demo|live|docker|dtest|ddemo|dlive}"
    exit 1
    ;;
esac
