#!/bin/bash
# Simple concurrency test for Kaggle Agent API

API_URL="https://rjmzoavoel.execute-api.us-west-2.amazonaws.com/prod/run"
EMAIL="teh93cat@gmail.com"

# Number of parallel runs
CONCURRENCY=50

# Competition to test (use open/public competitions only)
COMP_URL="https://www.kaggle.com/competitions/titanic"

echo " Starting $CONCURRENCY concurrent requests to $API_URL"

seq 1 $CONCURRENCY | xargs -n1 -P$CONCURRENCY bash -c '
  i=$0
  echo "→ Starting job $i"
  curl -s -X POST "$API_URL?url=$COMP_URL&email=$EMAIL" -w " [HTTP %{http_code}]\n"
'

echo "All requests dispatched. Check DynamoDB and CloudWatch for parallel execution behavior."
