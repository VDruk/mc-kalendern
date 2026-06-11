CREATE TABLE IF NOT EXISTS counts (
  event_id TEXT PRIMARY KEY,
  n INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rl (
  ip_hash  TEXT NOT NULL,
  event_id TEXT NOT NULL,
  day      TEXT NOT NULL,
  c        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (ip_hash, event_id, day)
);
