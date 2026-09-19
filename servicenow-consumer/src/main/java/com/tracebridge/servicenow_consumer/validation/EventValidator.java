package com.tracebridge.servicenow_consumer.validation;

import com.tracebridge.servicenow_consumer.event.ServiceRequestCreatedEvent;
import com.tracebridge.servicenow_consumer.exception.InvalidEventException;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

@Component
public class EventValidator {

    public void validate(ServiceRequestCreatedEvent event) {
        if (event.eventId() == null) {
            throw new InvalidEventException("eventId is missing");
        }
        if (event.correlationId() == null) {
            throw new InvalidEventException("correlationId is missing");
        }
        if (event.occurredAt() == null) {
            throw new InvalidEventException("occurredAt is missing");
        }
        if (!StringUtils.hasText(event.source())) {
            throw new InvalidEventException("source is missing");
        }
        if (!ServiceRequestCreatedEvent.SUPPORTED_EVENT_TYPE.equals(event.eventType())) {
            throw new InvalidEventException("unsupported eventType: " + event.eventType());
        }
        if (event.eventVersion() == null || event.eventVersion() != ServiceRequestCreatedEvent.SUPPORTED_EVENT_VERSION) {
            throw new InvalidEventException("unsupported eventVersion: " + event.eventVersion());
        }

        ServiceRequestCreatedEvent.Payload payload = event.payload();
        if (payload == null) {
            throw new InvalidEventException("payload is missing");
        }
        if (!StringUtils.hasText(payload.customerId())) {
            throw new InvalidEventException("payload.customerId is missing");
        }
        if (!StringUtils.hasText(payload.category())) {
            throw new InvalidEventException("payload.category is missing");
        }
        if (!StringUtils.hasText(payload.subcategory())) {
            throw new InvalidEventException("payload.subcategory is missing");
        }
        if (!StringUtils.hasText(payload.shortDescription())) {
            throw new InvalidEventException("payload.shortDescription is missing");
        }
        if (!StringUtils.hasText(payload.description())) {
            throw new InvalidEventException("payload.description is missing");
        }
        if (payload.priority() == null) {
            throw new InvalidEventException("payload.priority is missing");
        }
    }
}
