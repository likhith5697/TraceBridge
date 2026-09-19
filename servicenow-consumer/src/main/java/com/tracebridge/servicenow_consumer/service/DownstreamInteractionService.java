package com.tracebridge.servicenow_consumer.service;

import com.tracebridge.servicenow_consumer.entity.DownstreamInteraction;
import com.tracebridge.servicenow_consumer.entity.DownstreamInteractionStatus;
import com.tracebridge.servicenow_consumer.repository.DownstreamInteractionRepository;
import com.tracebridge.servicenow_consumer.servicenow.PayloadSanitizer;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowIncidentRequest;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowResult;
import java.time.Instant;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

@Service
public class DownstreamInteractionService {

    private static final Logger log = LoggerFactory.getLogger(DownstreamInteractionService.class);
    private static final String TARGET_SYSTEM = "SERVICENOW";
    private static final String OPERATION = "CREATE_INCIDENT";
    private static final int FIRST_ATTEMPT = 1;

    private final DownstreamInteractionRepository repository;
    private final PayloadSanitizer payloadSanitizer;
    private final ObjectMapper objectMapper;

    public DownstreamInteractionService(
            DownstreamInteractionRepository repository, PayloadSanitizer payloadSanitizer, ObjectMapper objectMapper) {
        this.repository = repository;
        this.payloadSanitizer = payloadSanitizer;
        this.objectMapper = objectMapper;
    }

    // The idempotency check: called BEFORE the ServiceNow request is made, so
    // a Kafka redelivery of the same event never triggers a second real call
    // in the first place - this is the check that actually avoids the
    // duplicate external side effect, not just a duplicate audit row.
    public boolean alreadyProcessed(UUID eventId) {
        return eventId != null && repository.existsByEventId(eventId);
    }

    public void record(
            UUID correlationId,
            UUID eventId,
            String endpoint,
            ServiceNowIncidentRequest requestBody,
            ServiceNowResult result,
            Instant requestTimestamp) {
        String requestJson = payloadSanitizer.sanitize(objectMapper.writeValueAsString(requestBody));
        String responseJson = payloadSanitizer.sanitize(result.rawResponseBody());

        DownstreamInteraction interaction = new DownstreamInteraction(
                correlationId,
                eventId,
                TARGET_SYSTEM,
                OPERATION,
                "POST",
                endpoint,
                requestJson,
                requestTimestamp,
                responseJson,
                Instant.now(),
                result.httpStatus(),
                result.success() ? DownstreamInteractionStatus.SUCCESS : DownstreamInteractionStatus.FAILED,
                result.errorCode(),
                result.errorMessage(),
                result.durationMs(),
                FIRST_ATTEMPT);

        try {
            repository.save(interaction);
        } catch (DataIntegrityViolationException e) {
            // Belt-and-suspenders: the alreadyProcessed() check above closes
            // this window for the normal case, but a genuine race (two
            // threads processing the same eventId at once) is only ever
            // prevented for certain by the database's own unique constraint.
            // By the time we're here the ServiceNow call already happened -
            // this only stops a duplicate audit row, logged, not thrown.
            log.atWarn()
                    .addKeyValue("event", "DUPLICATE_EVENT_DETECTED_ON_INSERT")
                    .addKeyValue("targetSystem", TARGET_SYSTEM)
                    .log("A downstream_interaction row for this eventId already exists - discarding the duplicate insert");
            return;
        }

        log.atInfo()
                .addKeyValue("event", "DOWNSTREAM_INTERACTION_PERSISTED")
                .addKeyValue("targetSystem", TARGET_SYSTEM)
                .addKeyValue("status", interaction.getStatus())
                .addKeyValue("httpStatus", result.httpStatus())
                .log("Persisted downstream interaction record");
    }
}
