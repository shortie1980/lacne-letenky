#!/usr/bin/env python3
"""Sledovanie lacných leteniek – spustenie jedného behu.

    python watcher.py               # normálny beh (GitHub Actions)
    python watcher.py --dry-run     # nič neposiela, neukladá stav upozornení; dáta pre web áno
    python watcher.py --test-notify # skúšobné upozornenie všetkými kanálmi
"""
from letenky.engine import main

if __name__ == "__main__":
    main()
