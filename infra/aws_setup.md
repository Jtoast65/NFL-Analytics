# AWS Setup — RDS Postgres + S3 (free tier)

Step-by-step to provision the cloud infrastructure for the orchestration pipeline.
Everything here fits the AWS Free Tier, but **a credit card is required** and you must
follow the teardown steps to avoid charges after the free window.

> Free-tier limits that matter here:
> - **RDS**: 750 hrs/month of a `db.t3.micro` (or `db.t4g.micro`) + 20 GB storage, for 12 months. One instance running continuously ≈ 750 hrs, so **run only one**.
> - **S3**: 5 GB storage, 20k GET / 2k PUT per month, for 12 months.
> - Backups, a second instance, or data egress can incur charges — see Teardown.

---

## 1. IAM user (programmatic access)

The pipeline (boto3 in Airflow) needs keys — never use your root account for this.

1. AWS Console → **IAM** → **Users** → **Create user**. Name: `nfl-pipeline`.
2. Do **not** enable console access (programmatic only).
3. Permissions → **Attach policies directly** → attach:
   - `AmazonS3FullAccess` (or scope to your bucket later)
   - `AmazonRDSFullAccess` (only needed if the DAG manages RDS; can drop to read-only)
4. Create user → open it → **Security credentials** → **Create access key** →
   use case **Application running outside AWS** → copy the **Access key ID** and **Secret access key**.
5. These become `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`.

## 2. S3 bucket

1. Console → **S3** → **Create bucket**.
2. Name: globally unique, e.g. `nfl-analytics-raw-<your-initials>` (record it as `S3_BUCKET`).
3. Region: pick one close to you and **use the same region for RDS** (e.g. `us-west-2`).
4. Leave "Block all public access" **ON** (the pipeline uses IAM keys, not public access).
5. Create.

## 3. RDS Postgres

1. Console → **RDS** → **Create database** → **Standard create**.
2. Engine: **PostgreSQL** (version 16.x).
3. Templates: **Free tier**.
4. Settings:
   - DB instance identifier: `nfl-analytics-db`
   - Master username: `postgres`
   - Master password: choose a strong one (record it; URL-encode special chars in the connection string later).
5. Instance config: `db.t3.micro` (or `db.t4g.micro` — free-tier eligible).
6. Storage: 20 GB, **disable** storage autoscaling (avoids surprise growth).
7. Connectivity:
   - **Public access: Yes** (needed so Render + your laptop can reach it; we lock it down with the security group + SSL).
   - VPC security group → **Create new** → name `nfl-db-sg`.
8. Additional config → Initial database name: `postgres`. Disable automated backups if you want to stay strictly free (optional; 20 GB backup is free-tier too).
9. Create database. Wait ~5–10 min for status **Available**, then copy the **endpoint** hostname.

## 4. Security group (network access)

Console → **EC2** → **Security Groups** → `nfl-db-sg` → **Inbound rules** → Edit:
- Type **PostgreSQL** (port 5432), Source **My IP** — for your laptop.
- Add a second rule Type **PostgreSQL**, Source `0.0.0.0/0` **only** if Render can't reach it otherwise
  (Render free tier has dynamic egress IPs). This is a tradeoff — mitigated by a strong password + SSL.

## 5. Enable pgvector on RDS

RDS Postgres 16 ships pgvector. Once the instance is Available, connect and enable it
(the RAG `documents` table gets migrated here in the next step):

```bash
psql "postgresql://postgres:PASSWORD@ENDPOINT:5432/postgres?sslmode=require" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## 6. Record everything in `.env`

Add to `~/nfl-analytics/.env` (already gitignored):

```
# --- AWS (Extension 2) ---
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-west-2
S3_BUCKET=nfl-analytics-raw-xyz

# Swap DATABASE_URL from Supabase to RDS once data is migrated (step handled in code):
# DATABASE_URL=postgresql://postgres:URLENCODED_PASSWORD@ENDPOINT:5432/postgres?sslmode=require
```

Keep the Supabase `DATABASE_URL` active until the migration is verified, then switch.

---

## Teardown (do this when you're done demoing — avoids charges)

1. **RDS** → select `nfl-analytics-db` → **Actions** → **Stop temporarily** (pauses billing for up to 7 days),
   or **Delete** (choose "no final snapshot" to avoid snapshot storage charges) when fully done.
2. **S3** → empty the bucket, then delete it.
3. **IAM** → deactivate/delete the `nfl-pipeline` access key.
4. Check **Billing → Free Tier** dashboard periodically; set a **Billing alarm** at $1 to be safe.

> Tip: a stopped RDS instance auto-starts after 7 days. If you're not demoing for a while,
> **delete** it (the code re-provisions/re-migrates cleanly) rather than leaving it stopped.
