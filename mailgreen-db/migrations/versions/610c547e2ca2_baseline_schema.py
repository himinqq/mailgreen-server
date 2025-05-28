revision = "610c547e2ca2"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op


# ────────── upgrade ──────────
def upgrade() -> None:
    op.execute(
        """
    /* ─────────────────────────────────────────────
       0. 확장 (uuid, 벡터)
    ───────────────────────────────────────────── */
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS vector;

    /* ─────────────────────────────────────────────
       1. ENUM 정의
    ───────────────────────────────────────────── */
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mail_action_type') THEN
            CREATE TYPE mail_action_type AS ENUM ('delete', 'archive', 'spam');
        END IF;
    END$$;

    /* ─────────────────────────────────────────────
       2. users
    ───────────────────────────────────────────── */
    CREATE TABLE users (
      id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      google_sub   VARCHAR(128) UNIQUE NOT NULL,
      email        VARCHAR(320) NOT NULL,
      name         VARCHAR(100),
      picture_url  TEXT,
      created_at   TIMESTAMPTZ DEFAULT now()
    );

    CREATE INDEX idx_users_email ON users(email);

    /* ─────────────────────────────────────────────
       3. user_notifications
    ───────────────────────────────────────────── */
    CREATE TABLE user_notifications (
      user_id      UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
      interval_hr  INT  DEFAULT 24,
      last_sent_at TIMESTAMPTZ
    );

    /* ─────────────────────────────────────────────
       4. mail_embeddings
    ───────────────────────────────────────────── */
    CREATE TABLE mail_embeddings (
      id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      gmail_msg_id        VARCHAR(32) UNIQUE NOT NULL,
      thread_id           VARCHAR(32),
      sender              VARCHAR(320),
      subject             TEXT,
      snippet             TEXT,
      labels              TEXT[],
      size_bytes          INT,
      is_read             BOOLEAN,
      is_starred          BOOLEAN,
      received_at         TIMESTAMPTZ,
      vector              vector(768),
      keywords            TEXT[],
      carbon_factor       DOUBLE PRECISION DEFAULT 0.00002,
      carbon_saved_grams  DOUBLE PRECISION DEFAULT 0,
      processed_at        TIMESTAMPTZ DEFAULT now()
    );

    CREATE INDEX hnsw_mail_vec_idx ON mail_embeddings
      USING hnsw (vector vector_l2_ops)
      WITH (m = 16, ef_construction = 200);

    CREATE INDEX idx_mail_user_sender ON mail_embeddings(user_id, sender);
    CREATE INDEX idx_mail_unread ON mail_embeddings(user_id, is_read)
      WHERE is_read = false;
    CREATE INDEX idx_mail_recent ON mail_embeddings(user_id, received_at DESC);

    /* ─────────────────────────────────────────────
       5. mail_keywords
    ───────────────────────────────────────────── */
    CREATE TABLE mail_keywords (
      mail_id  UUID REFERENCES mail_embeddings(id) ON DELETE CASCADE,
      keyword  VARCHAR(100),
      weight   REAL,
      PRIMARY KEY (mail_id, keyword)
    );

    CREATE INDEX idx_kw_keyword ON mail_keywords(keyword);

    /* ─────────────────────────────────────────────
       6. mail_actions
    ───────────────────────────────────────────── */
    CREATE TABLE mail_actions (
      id            SERIAL PRIMARY KEY,
      mail_id       UUID REFERENCES mail_embeddings(id) ON DELETE CASCADE,
      user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
      action        mail_action_type,
      action_ts     TIMESTAMPTZ DEFAULT now(),
      carbon_saved  DOUBLE PRECISION
    );

    CREATE INDEX idx_action_user_ts ON mail_actions(user_id, action_ts DESC);

    /* ─────────────────────────────────────────────
       7. analysis_tasks
    ───────────────────────────────────────────── */
    CREATE TABLE analysis_tasks (
      id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
      task_type     VARCHAR(50),
      status        VARCHAR(20),
      progress_pct  INT CHECK (progress_pct BETWEEN 0 AND 100),
      started_at    TIMESTAMPTZ,
      finished_at   TIMESTAMPTZ,
      error_msg     TEXT
    );

    CREATE INDEX idx_task_user_time ON analysis_tasks(user_id, started_at DESC);

    /* ─────────────────────────────────────────────
       8. carbon_effects (관리자 편집 테이블)
    ───────────────────────────────────────────── */
    CREATE TABLE carbon_effects (
      id          SERIAL PRIMARY KEY,
      title       VARCHAR(100),
      image_url   TEXT,
      grams_min   INT,
      grams_max   INT,
      description TEXT,
      updated_at  TIMESTAMPTZ DEFAULT now()
    );
    """
    )


# ────────── downgrade ──────────
def downgrade() -> None:
    op.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
