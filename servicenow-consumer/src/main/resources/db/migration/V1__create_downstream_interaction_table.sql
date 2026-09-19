CREATE TABLE downstream_interaction (
    id                  BIGSERIAL PRIMARY KEY,
    correlation_id      UUID NOT NULL,
    target_system       VARCHAR(50) NOT NULL,
    operation           VARCHAR(50) NOT NULL,
    http_method         VARCHAR(10) NOT NULL,
    endpoint            VARCHAR(500) NOT NULL,
    request_payload     JSONB,
    request_timestamp   TIMESTAMPTZ NOT NULL,
    response_payload    JSONB,
    response_timestamp  TIMESTAMPTZ,
    http_status         INTEGER,
    status              VARCHAR(20) NOT NULL,
    error_code          VARCHAR(100),
    error_message       VARCHAR(2000),
    duration_ms         BIGINT NOT NULL,
    attempt_number      INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_downstream_interaction_correlation_id ON downstream_interaction (correlation_id);
