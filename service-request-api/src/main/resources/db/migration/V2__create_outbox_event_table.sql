-- The Outbox Pattern: closes the "saved to Postgres but Kafka never heard
-- about it" gap. The business row (service_request) and this outbox row
-- are written in ONE database transaction (see ServiceRequestService),
-- so it is physically impossible for one to commit without the other. A
-- separate poller (OutboxPublisher) then actually calls Kafka and marks
-- sent = true once Kafka confirms receipt - if Kafka is briefly
-- unreachable, the row just stays unsent and gets retried next cycle,
-- instead of the event being silently lost.
CREATE TABLE outbox_event (
    id                 BIGSERIAL PRIMARY KEY,
    correlation_id     UUID NOT NULL,
    event_id           UUID NOT NULL UNIQUE,
    topic              VARCHAR(200) NOT NULL,
    payload            TEXT NOT NULL,
    sent               BOOLEAN NOT NULL DEFAULT FALSE,
    attempt_count      INTEGER NOT NULL DEFAULT 0,
    last_error         VARCHAR(2000),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at            TIMESTAMPTZ
);

-- Partial index: only unsent rows ever need to be found by the poller, and
-- sent rows drop out of this index entirely once marked, keeping it small
-- regardless of how many events have accumulated historically.
CREATE INDEX idx_outbox_event_unsent ON outbox_event (created_at) WHERE sent = FALSE;
