package com.tracebridge.service_request_api.event;

import com.tracebridge.service_request_api.entity.OutboxEvent;
import com.tracebridge.service_request_api.repository.OutboxEventRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

// Writes the outbox row - always called from within the SAME transaction
// as the ServiceRequest save (see ServiceRequestService), never on its own.
// That single fact is the entire mechanism: Spring Data JPA's save() here
// joins the caller's existing transaction rather than opening its own, so
// the business row and this row commit together or not at all.
@Service
public class OutboxEventService {

    private static final Logger log = LoggerFactory.getLogger(OutboxEventService.class);

    private final OutboxEventRepository repository;
    private final ObjectMapper objectMapper;
    private final String topic;

    public OutboxEventService(
            OutboxEventRepository repository,
            ObjectMapper objectMapper,
            @Value("${tracebridge.kafka.topic.service-request-created}") String topic) {
        this.repository = repository;
        this.objectMapper = objectMapper;
        this.topic = topic;
    }

    public void enqueue(ServiceRequestCreatedEvent event) {
        // Serialized once, here, at the moment of truth - what gets published
        // later is exactly these bytes, never re-serialized, so there is no
        // risk of the durably-recorded payload drifting from what Kafka
        // actually receives.
        String payload = objectMapper.writeValueAsString(event);

        OutboxEvent outboxEvent = new OutboxEvent(event.correlationId(), event.eventId(), topic, payload);
        repository.save(outboxEvent);

        log.atInfo().addKeyValue("event", "OUTBOX_EVENT_QUEUED").log("Queued event for Kafka publish");
    }
}
