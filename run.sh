#!/bin/bash

# Exit immediately if a command fails
set -e

# Check arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: ./run.sh <file1.pdf> <file2.pdf>"
    exit 1
fi

FILE1=$1
FILE2=$2

# Upgrade pip (optional but good practice)
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Run your program
python run.py "$FILE1" "$FILE2"