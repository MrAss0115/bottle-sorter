CREATE TABLE IF NOT EXISTS reward_events (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device TEXT COLLATE BINARY NOT NULL,
    batch INTEGER NOT NULL CHECK(batch BETWEEN 1 AND 4294967295),
    uid TEXT COLLATE BINARY NOT NULL,
    earned INTEGER NOT NULL CHECK(earned BETWEEN 0 AND 4294967295),
    total INTEGER NOT NULL CHECK(total BETWEEN earned AND 4294967295),
    bottles INTEGER NOT NULL CHECK(bottles BETWEEN 0 AND 5),
    cans INTEGER NOT NULL CHECK(cans BETWEEN 0 AND 5),
    rejected INTEGER NOT NULL CHECK(rejected BETWEEN 0 AND 5),
    received_at TEXT NOT NULL,
    UNIQUE(device, batch),
    CHECK(bottles + cans + rejected BETWEEN 1 AND 5),
    CHECK((bottles+cans=0 AND earned=0) OR
          (bottles+cans>0 AND earned>0 AND earned%(bottles+cans)=0))
);
CREATE INDEX IF NOT EXISTS rewards_by_card ON reward_events(device, uid, batch DESC);
CREATE INDEX IF NOT EXISTS rewards_by_uid ON reward_events(uid, record_id DESC);
