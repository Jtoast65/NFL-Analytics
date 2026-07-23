.PHONY: install db-init ingest train serve test lint

install:
	pip install -r requirements.txt

db-init:
	python -c "from dotenv import load_dotenv; import os; load_dotenv(); url=os.environ['DATABASE_URL']; \
	           import subprocess; subprocess.run(['psql', url, '-f', 'schema/init.sql'], check=True)"

ingest:
	python ingestion/ingest_games.py
	python ingestion/ingest_players.py
	python ingestion/ingest_plays.py
	python ingestion/ingest_player_stats.py

train:
	python models/train.py

serve:
	uvicorn api.main:app --reload --port 8000

test:
	pytest tests/ -v

dashboard:
	streamlit run dashboard/app.py

lint:
	python -m py_compile ingestion/*.py features/*.py models/*.py api/main.py
