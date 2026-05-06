#!/bin/bash

cd "$(dirname "$0")" || exit 1

rm ../logs/*.txt ../logs/workers/*.txt
