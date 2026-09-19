package com.tracebridge.servicenow_consumer.event;

import java.time.Instant;
import java.util.UUID;

public record ServiceRequestCreatedEvent(
        UUID eventId,
        String eventType,
        Integer eventVersion,
        Instant occurredAt,
        UUID correlationId,
        String source,
        Payload payload) {

    public static final String SUPPORTED_EVENT_TYPE = "SERVICE_REQUEST_CREATED";
    public static final int SUPPORTED_EVENT_VERSION = 1;

    public record Payload(
            String customerId,
            String category,
            String subcategory,
            String shortDescription,
            String description,
            Priority priority) {}
}
