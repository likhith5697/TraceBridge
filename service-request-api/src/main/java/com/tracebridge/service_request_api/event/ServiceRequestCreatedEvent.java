package com.tracebridge.service_request_api.event;

import com.tracebridge.service_request_api.entity.Priority;
import java.time.Instant;
import java.util.UUID;

public record ServiceRequestCreatedEvent(
        UUID eventId,
        String eventType,
        int eventVersion,
        Instant occurredAt,
        UUID correlationId,
        String source,
        Payload payload) {

    public static final String EVENT_TYPE = "SERVICE_REQUEST_CREATED";
    public static final int EVENT_VERSION = 1;

    public record Payload(
            String customerId,
            String category,
            String subcategory,
            String shortDescription,
            String description,
            Priority priority) {}
}
