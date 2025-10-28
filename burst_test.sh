#!/bin/bash
API_URL="https://rjmzoavoel.execute-api.us-west-2.amazonaws.com/prod/run"
EMAIL="teh93cat@gmail.com"
COMP_URL="https://www.kaggle.com/competitions/titanic"

for i in {1..10}; do
  echo "→ Triggering job $i"
  curl -s -X POST "$API_URL?url=$COMP_URL&email=$EMAIL" &
done
wait
echo "10 concurrent requests fired."
