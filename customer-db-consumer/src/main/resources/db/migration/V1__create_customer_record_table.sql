CREATE SCHEMA IF NOT EXISTS customer_db_consumer;

-- One row per successfully processed SERVICE_REQUEST_CREATED event - this is
-- the actual business data customer-db-consumer is responsible for writing.
-- There is deliberately no per-attempt outcome/audit row here the way
-- servicenow-consumer has downstream_interaction: the dependency this consumer
-- can fail against *is* this same Postgres, so there is nowhere safe to
-- persist a "the database write failed" record when the database itself is
-- what's unavailable. That failure is observed through structured logs
-- (search_logs) instead - see CustomerRecordService.
CREATE TABLE customer_db_consumer.customer_record (
    id BIGSERIAL PRIMARY KEY,
    correlation_id UUID NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100) NOT NULL,
    short_description VARCHAR(500) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_customer_record_correlation_id ON customer_db_consumer.customer_record (correlation_id);
