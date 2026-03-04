-- Placeholder migration for events table
-- Fill in with proper up/down for your migration framework

CREATE TABLE events (
  id BIGSERIAL PRIMARY KEY,
  event_id UUID NOT NULL UNIQUE,
  user_id BIGINT NOT NULL,
  type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  read BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX idx_events_user_created_desc ON events (user_id, created_at DESC);
CREATE INDEX idx_events_user_unread ON events (user_id) WHERE read = false;

-- Consider PARTITION BY RANGE (created_at) for retention and performance
