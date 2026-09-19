package com.tracebridge.customer_db_consumer.validation;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.tracebridge.customer_db_consumer.event.Priority;
import com.tracebridge.customer_db_consumer.event.ServiceRequestCreatedEvent;
import com.tracebridge.customer_db_consumer.exception.InvalidEventException;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class EventValidatorTest {

    private final EventValidator validator = new EventValidator();

    private ServiceRequestCreatedEvent validEvent() {
        return new ServiceRequestCreatedEvent(
                UUID.randomUUID(),
                ServiceRequestCreatedEvent.SUPPORTED_EVENT_TYPE,
                ServiceRequestCreatedEvent.SUPPORTED_EVENT_VERSION,
                Instant.now(),
                UUID.randomUUID(),
                "CUSTOMER_PORTAL",
                new ServiceRequestCreatedEvent.Payload(
                        "cust-1", "billing", "invoice", "short desc", "long desc", Priority.P2));
    }

    @Test
    void accepts_a_fully_populated_event() {
        validator.validate(validEvent());
    }

    @Test
    void rejects_missing_correlation_id() {
        ServiceRequestCreatedEvent event = validEvent();
        ServiceRequestCreatedEvent withoutCorrelationId = new ServiceRequestCreatedEvent(
                event.eventId(), event.eventType(), event.eventVersion(), event.occurredAt(),
                null, event.source(), event.payload());

        assertThatThrownBy(() -> validator.validate(withoutCorrelationId))
                .isInstanceOf(InvalidEventException.class)
                .hasMessageContaining("correlationId");
    }

    @Test
    void rejects_unsupported_event_type() {
        ServiceRequestCreatedEvent event = validEvent();
        ServiceRequestCreatedEvent wrongType = new ServiceRequestCreatedEvent(
                event.eventId(), "SOMETHING_ELSE", event.eventVersion(), event.occurredAt(),
                event.correlationId(), event.source(), event.payload());

        assertThatThrownBy(() -> validator.validate(wrongType))
                .isInstanceOf(InvalidEventException.class)
                .hasMessageContaining("eventType");
    }

    @Test
    void rejects_missing_payload_customer_id() {
        ServiceRequestCreatedEvent event = validEvent();
        ServiceRequestCreatedEvent.Payload badPayload = new ServiceRequestCreatedEvent.Payload(
                "", "billing", "invoice", "short desc", "long desc", Priority.P2);
        ServiceRequestCreatedEvent withBadPayload = new ServiceRequestCreatedEvent(
                event.eventId(), event.eventType(), event.eventVersion(), event.occurredAt(),
                event.correlationId(), event.source(), badPayload);

        assertThatThrownBy(() -> validator.validate(withBadPayload))
                .isInstanceOf(InvalidEventException.class)
                .hasMessageContaining("customerId");
    }
}
