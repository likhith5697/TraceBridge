package com.tracebridge.servicenow_consumer.validation;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.tracebridge.servicenow_consumer.event.Priority;
import com.tracebridge.servicenow_consumer.event.ServiceRequestCreatedEvent;
import com.tracebridge.servicenow_consumer.exception.InvalidEventException;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class EventValidatorTest {

    private final EventValidator validator = new EventValidator();

    private ServiceRequestCreatedEvent.Payload validPayload() {
        return new ServiceRequestCreatedEvent.Payload(
                "CUS-1", "NETWORK", "CONNECTIVITY", "short desc", "full description", Priority.P2);
    }

    private ServiceRequestCreatedEvent validEvent() {
        return new ServiceRequestCreatedEvent(
                UUID.randomUUID(),
                ServiceRequestCreatedEvent.SUPPORTED_EVENT_TYPE,
                ServiceRequestCreatedEvent.SUPPORTED_EVENT_VERSION,
                Instant.now(),
                UUID.randomUUID(),
                "CUSTOMER_PORTAL",
                validPayload());
    }

    @Test
    void acceptsAValidEvent() {
        assertThatCode(() -> validator.validate(validEvent())).doesNotThrowAnyException();
    }

    @Test
    void rejectsUnsupportedEventType() {
        ServiceRequestCreatedEvent event = validEvent();
        ServiceRequestCreatedEvent invalid = new ServiceRequestCreatedEvent(
                event.eventId(), "SOMETHING_ELSE", event.eventVersion(), event.occurredAt(),
                event.correlationId(), event.source(), event.payload());

        assertThatThrownBy(() -> validator.validate(invalid)).isInstanceOf(InvalidEventException.class);
    }

    @Test
    void rejectsUnsupportedEventVersion() {
        ServiceRequestCreatedEvent event = validEvent();
        ServiceRequestCreatedEvent invalid = new ServiceRequestCreatedEvent(
                event.eventId(), event.eventType(), 2, event.occurredAt(),
                event.correlationId(), event.source(), event.payload());

        assertThatThrownBy(() -> validator.validate(invalid)).isInstanceOf(InvalidEventException.class);
    }

    @Test
    void rejectsMissingCorrelationId() {
        ServiceRequestCreatedEvent event = validEvent();
        ServiceRequestCreatedEvent invalid = new ServiceRequestCreatedEvent(
                event.eventId(), event.eventType(), event.eventVersion(), event.occurredAt(),
                null, event.source(), event.payload());

        assertThatThrownBy(() -> validator.validate(invalid)).isInstanceOf(InvalidEventException.class);
    }

    @Test
    void rejectsMissingPayload() {
        ServiceRequestCreatedEvent event = validEvent();
        ServiceRequestCreatedEvent invalid = new ServiceRequestCreatedEvent(
                event.eventId(), event.eventType(), event.eventVersion(), event.occurredAt(),
                event.correlationId(), event.source(), null);

        assertThatThrownBy(() -> validator.validate(invalid)).isInstanceOf(InvalidEventException.class);
    }

    @Test
    void rejectsBlankShortDescription() {
        ServiceRequestCreatedEvent.Payload payload = new ServiceRequestCreatedEvent.Payload(
                "CUS-1", "NETWORK", "CONNECTIVITY", "  ", "full description", Priority.P2);
        ServiceRequestCreatedEvent event = validEvent();
        ServiceRequestCreatedEvent invalid = new ServiceRequestCreatedEvent(
                event.eventId(), event.eventType(), event.eventVersion(), event.occurredAt(),
                event.correlationId(), event.source(), payload);

        assertThatThrownBy(() -> validator.validate(invalid)).isInstanceOf(InvalidEventException.class);
    }
}
