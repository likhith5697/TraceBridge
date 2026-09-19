CREATE TABLE service_request (
    id                 BIGSERIAL PRIMARY KEY,
    correlation_id     UUID NOT NULL UNIQUE,
    source             VARCHAR(50) NOT NULL,
    customer_id        VARCHAR(50) NOT NULL,
    category           VARCHAR(50) NOT NULL,
    subcategory        VARCHAR(50) NOT NULL,
    short_description  VARCHAR(255) NOT NULL,
    description        VARCHAR(2000) NOT NULL,
    priority           VARCHAR(10) NOT NULL,
    status             VARCHAR(30) NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
