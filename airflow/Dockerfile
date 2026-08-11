# Astro Runtime = a supported Airflow build. Bump with `astro dev upgrade` if needed.
FROM quay.io/astronomer/astro-runtime:12.7.1

# dbt and the project's ML/RAG deps go in isolated venvs so their transitive pins
# never conflict with Airflow (installing dbt-core into the Airflow env caused a
# pip ResolutionTooDeep). The DAG's BashOperators invoke these venvs by path.
COPY dbt_requirements.txt project_requirements.txt /tmp/

RUN python -m venv /usr/local/airflow/dbt_venv && \
    /usr/local/airflow/dbt_venv/bin/pip install --no-cache-dir -r /tmp/dbt_requirements.txt

RUN python -m venv /usr/local/airflow/project_venv && \
    /usr/local/airflow/project_venv/bin/pip install --no-cache-dir -r /tmp/project_requirements.txt
