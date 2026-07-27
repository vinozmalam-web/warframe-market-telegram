#!/bin/bash

cd /home/edcsod/warframe-market-telegram

git pull

docker compose build
docker compose down
docker compose up -d

docker system prune -a -f
