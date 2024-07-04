#!/bin/bash

# Check if both arguments are provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <key> <value>"
    exit 1
fi

KEY=$1
VALUE=$2
CONFIG_FILE="/home/danny/bug_zapper/config.json"

# Update the JSON file
temp=$(mktemp)
jq ".$KEY = $VALUE" $CONFIG_FILE > "$temp" && mv "$temp" $CONFIG_FILE

echo "Updated $KEY to $VALUE in $CONFIG_FILE"
