-- Kafka gives at-least-once delivery, not exactly-once: a redelivered event
-- (after a crash before offset commit, a rebalance, or a manual offset
-- reset) would otherwise call ServiceNow again and persist a second row for
-- the same correlation_id, with no way to tell it apart from the original.
--
-- event_id is a UUID generated once per event by service-request-api - it
-- never changes across redeliveries, which is what makes it usable as an
-- idempotency key. The unique index is the real safety net (enforced by
-- Postgres itself, race-safe); the application-level check before calling
-- ServiceNow is what actually avoids the duplicate external side effect.
--
-- Nullable because existing historical rows were written before this
-- column existed - a plain unique index treats every NULL as distinct, so
-- those rows are unaffected and every new row going forward gets a real,
-- enforced-unique event_id.
ALTER TABLE downstream_interaction ADD COLUMN event_id UUID;

CREATE UNIQUE INDEX uq_downstream_interaction_event_id ON downstream_interaction (event_id);
