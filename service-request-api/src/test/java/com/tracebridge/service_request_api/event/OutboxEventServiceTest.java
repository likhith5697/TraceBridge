package com.tracebridge.service_request_api.event;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;

import com.tracebridge.service_request_api.entity.OutboxEvent;
import com.tracebridge.service_request_api.entity.Priority;
import com.tracebridge.service_request_api.repository.OutboxEventRepository;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import tools.jackson.databind.json.JsonMapper;

@ExtendWith(MockitoExtension.class)
class OutboxEventServiceTest {

    private static final String TOPIC = "servicenow.service-request";

    @Mock
    private OutboxEventRepository repository;

    // Built in @BeforeEach, not as a field initializer: field initializers run
    // during test-instance construction, BEFORE MockitoExtension injects the
    // @Mock fields above - constructing this eagerly would capture a null
    // repository.
    private OutboxEventService service;

    @BeforeEach
    void setUp() {
        service = new OutboxEventService(repository, JsonMapper.builder().build(), TOPIC);
    }

    private ServiceRequestCreatedEvent event() {
        return new ServiceRequestCreatedEvent(
                UUID.randomUUID(),
                ServiceRequestCreatedEvent.EVENT_TYPE,
                ServiceRequestCreatedEvent.EVENT_VERSION,
                Instant.now(),
                UUID.randomUUID(),
                "CUSTOMER_PORTAL",
                new ServiceRequestCreatedEvent.Payload(
                        "cust-1", "billing", "invoice", "short", "long", Priority.P2));
    }

    @Test
    void savesOneRowWithTheCorrelationIdEventIdTopicAndSerializedPayload() {
        ServiceRequestCreatedEvent event = event();

        service.enqueue(event);

        ArgumentCaptor<OutboxEvent> captor = ArgumentCaptor.forClass(OutboxEvent.class);
        verify(repository).save(captor.capture());
        OutboxEvent saved = captor.getValue();

        assertThat(saved.getCorrelationId()).isEqualTo(event.correlationId());
        assertThat(saved.getEventId()).isEqualTo(event.eventId());
        assertThat(saved.getTopic()).isEqualTo(TOPIC);
        assertThat(saved.isSent()).isFalse();
        assertThat(saved.getAttemptCount()).isZero();
        assertThat(saved.getPayload()).contains("cust-1").contains(event.correlationId().toString());
    }
}
