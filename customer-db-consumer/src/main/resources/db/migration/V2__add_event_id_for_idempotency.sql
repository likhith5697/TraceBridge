-- Same idempotency key as servicenow-consumer's downstream_interaction -
-- see that module's V2 migration for the full reasoning. One difference
-- here: a row in this table only ever exists after a SUCCESSFUL write (see
-- V1's comment on why failures aren't recorded), so this check naturally
-- only blocks a redelivery from duplicating an already-successful write. A
-- redelivery of an event whose first attempt failed is correctly allowed to
-- retry - there is no duplicate-side-effect risk, since nothing was written
-- the first time.
ALTER TABLE customer_record ADD COLUMN event_id UUID;

CREATE UNIQUE INDEX uq_customer_record_event_id ON customer_record (event_id);
