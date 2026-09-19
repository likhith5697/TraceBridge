package com.tracebridge.servicenow_consumer.service;

import com.tracebridge.servicenow_consumer.event.ServiceRequestCreatedEvent;
import com.tracebridge.servicenow_consumer.exception.CorrelationMismatchException;
import com.tracebridge.servicenow_consumer.exception.InvalidEventException;
import com.tracebridge.servicenow_consumer.exception.UnsupportedSourceException;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowClient;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowIncidentMapper;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowIncidentRequest;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowResult;
import com.tracebridge.servicenow_consumer.validation.CorrelationValidator;
import com.tracebridge.servicenow_consumer.validation.EventValidator;
import com.tracebridge.servicenow_consumer.validation.SourceValidator;
import java.time.Instant;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Service;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

// Orchestrates one Kafka record from raw JSON through to a persisted downstream_interaction
// row. Each collaborator owns exactly one responsibility - this class only sequences them.
//
// MDC note: this runs on a Spring Kafka consumer thread that is reused across every record
// in the topic, not a fresh thread per record like an HTTP request. The try/finally below is
// what stops one record's correlationId/eventId from leaking into the next record's log lines
// if this thread picks up another record afterward.
@Service
public class ServiceRequestEventProcessor {

    private static final Logger log = LoggerFactory.getLogger(ServiceRequestEventProcessor.class);

    private final ObjectMapper objectMapper;
    private final EventValidator eventValidator;
    private final CorrelationValidator correlationValidator;
    private final SourceValidator sourceValidator;
    private final ServiceNowIncidentMapper incidentMapper;
    private final ServiceNowClient serviceNowClient;
    private final DownstreamInteractionService downstreamInteractionService;

    public ServiceRequestEventProcessor(
            ObjectMapper objectMapper,
            EventValidator eventValidator,
            CorrelationValidator correlationValidator,
            SourceValidator sourceValidator,
            ServiceNowIncidentMapper incidentMapper,
            ServiceNowClient serviceNowClient,
            DownstreamInteractionService downstreamInteractionService) {
        this.objectMapper = objectMapper;
        this.eventValidator = eventValidator;
        this.correlationValidator = correlationValidator;
        this.sourceValidator = sourceValidator;
        this.incidentMapper = incidentMapper;
        this.serviceNowClient = serviceNowClient;
        this.downstreamInteractionService = downstreamInteractionService;
    }

    public void process(String rawEventJson, String headerCorrelationId) {
        try {
            processInternal(rawEventJson, headerCorrelationId);
        } finally {
            MDC.clear();
        }
    }

    private void processInternal(String rawEventJson, String headerCorrelationId) {
        long start = System.currentTimeMillis();
        ServiceRequestCreatedEvent event;
        try {
            event = objectMapper.readValue(rawEventJson, ServiceRequestCreatedEvent.class);
        } catch (JacksonException e) {
            log.atError()
                    .addKeyValue("event", "EVENT_VALIDATION_FAILED")
                    .addKeyValue("errorMessage", "malformed JSON: " + e.getMessage())
                    .log("Discarding unparseable Kafka record");
            return;
        }

        if (event.correlationId() != null) {
            MDC.put("correlationId", event.correlationId().toString());
        }
        if (event.eventId() != null) {
            MDC.put("eventId", event.eventId().toString());
        }

        log.atInfo()
                .addKeyValue("event", "KAFKA_CONSUMED")
                .addKeyValue("eventType", event.eventType())
                .log("Consumed event from Kafka");

        try {
            correlationValidator.validate(event.correlationId(), headerCorrelationId);
            log.atInfo().addKeyValue("event", "CORRELATION_VALIDATED").log("correlationId header matches event body");

            eventValidator.validate(event);
            log.atInfo().addKeyValue("event", "EVENT_VALIDATED").log("Event structure and metadata are valid");

            sourceValidator.validate(event.source());
            log.atInfo()
                    .addKeyValue("event", "SOURCE_VALIDATED")
                    .addKeyValue("source", event.source())
                    .log("Event source is supported");
        } catch (CorrelationMismatchException e) {
            log.atError()
                    .addKeyValue("event", "CORRELATION_MISMATCH")
                    .addKeyValue("errorMessage", e.getMessage())
                    .log("Correlation header does not match event body - skipping ServiceNow call");
            return;
        } catch (InvalidEventException | UnsupportedSourceException e) {
            log.atError()
                    .addKeyValue("event", "EVENT_VALIDATION_FAILED")
                    .addKeyValue("errorMessage", e.getMessage())
                    .log("Event failed validation - skipping ServiceNow call");
            return;
        }

        // Idempotency guard: Kafka only promises at-least-once delivery. If this
        // exact event was already processed (a redelivery after a crash before
        // offset commit, a rebalance, or a manual offset reset), stop here -
        // before calling ServiceNow again and creating a duplicate incident.
        if (downstreamInteractionService.alreadyProcessed(event.eventId())) {
            log.atWarn()
                    .addKeyValue("event", "DUPLICATE_EVENT_SKIPPED")
                    .addKeyValue("targetSystem", "SERVICENOW")
                    .log("eventId already has a recorded downstream interaction - skipping duplicate delivery");
            return;
        }

        ServiceNowIncidentRequest incidentRequest = incidentMapper.toIncidentRequest(event);
        log.atInfo().addKeyValue("event", "PAYLOAD_TRANSFORMED").log("Mapped event to ServiceNow incident request");

        Instant requestTimestamp = Instant.now();
        log.atInfo()
                .addKeyValue("event", "DOWNSTREAM_REQUEST_STARTED")
                .addKeyValue("targetSystem", "SERVICENOW")
                .log("Calling ServiceNow to create incident");

        ServiceNowResult result = serviceNowClient.createIncident(incidentRequest, event.correlationId().toString());

        if (result.success()) {
            log.atInfo()
                    .addKeyValue("event", "DOWNSTREAM_RESPONSE_RECEIVED")
                    .addKeyValue("targetSystem", "SERVICENOW")
                    .addKeyValue("httpStatus", result.httpStatus())
                    .addKeyValue("status", "SUCCESS")
                    .addKeyValue("durationMs", result.durationMs())
                    .log("ServiceNow incident created: {}", result.number());
        } else {
            log.atError()
                    .addKeyValue("event", "DOWNSTREAM_REQUEST_FAILED")
                    .addKeyValue("targetSystem", "SERVICENOW")
                    .addKeyValue("httpStatus", result.httpStatus())
                    .addKeyValue("status", "FAILED")
                    .addKeyValue("errorCode", result.errorCode())
                    .addKeyValue("durationMs", result.durationMs())
                    .log("ServiceNow incident creation failed");
        }

        downstreamInteractionService.record(
                event.correlationId(),
                event.eventId(),
                serviceNowClient.endpoint(),
                incidentRequest,
                result,
                requestTimestamp);

        long totalDurationMs = System.currentTimeMillis() - start;
        log.atInfo()
                .addKeyValue("event", "EVENT_PROCESSING_COMPLETED")
                .addKeyValue("durationMs", totalDurationMs)
                .log("Finished processing event");
    }
}
