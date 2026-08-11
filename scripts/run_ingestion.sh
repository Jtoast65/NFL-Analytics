#!/bin/bash
# One-time full ingestion: runs all 9 seasons (2016-2024).
# Run this in your own terminal — it takes 10-20 min total.
# Usage:  bash scripts/run_ingestion.sh
#         bash scripts/run_ingestion.sh 2024        # single season
set -e

SEASON=${1:-"all"}
VENV=".venv/bin/python"

echo "========================================"
echo " NFL Analytics — Full Ingestion"
echo "========================================"

if [ "$SEASON" = "all" ]; then
    YEARS="2016 2017 2018 2019 2020 2021 2022 2023 2024"
else
    YEARS="$SEASON"
fi

echo ""
echo "Step 1/3: Ingesting plays..."
for year in $YEARS; do
    echo "  Season $year"
    $VENV ingestion/ingest_plays.py --seasons $year
done

echo ""
echo "Step 2/3: Ingesting player stats..."
$VENV ingestion/ingest_player_stats.py

echo ""
echo "Step 3/3: Verifying row counts..."
$VENV -c "
from dotenv import load_dotenv; import os, psycopg2
load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
for table in ['games','players','plays','player_stats']:
    cur.execute(f'SELECT COUNT(*) FROM {table}')
    print(f'  {table}: {cur.fetchone()[0]:,} rows')
conn.close()
"

echo ""
echo "Ingestion complete."
