package com.tracebridge.customer_db_consumer.service;

import com.tracebridge.customer_db_consumer.event.ServiceRequestCreatedEvent;
import com.tracebridge.customer_db_consumer.exception.CorrelationMismatchException;
import com.tracebridge.customer_db_consumer.exception.InvalidEventException;
import com.tracebridge.customer_db_consumer.exception.UnsupportedSourceException;
import com.tracebridge.customer_db_consumer.validation.CorrelationValidator;
import com.tracebridge.customer_db_consumer.validation.EventValidator;
import com.tracebridge.customer_db_consumer.validation.SourceValidator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Service;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

// Orchestrates one Kafka record from raw JSON through to a persisted
// customer_record row. This is the same shape as
// servicenow-consumer's ServiceRequestEventProcessor, consuming the identical
// Kafka topic independently (a separate consumer group) - one consumer's
// outcome for a given correlationId has no bearing on the other's.
@Service
public class ServiceRequestEventProcessor {

    private static final Logger log = LoggerFactory.getLogger(ServiceRequestEventProcessor.class);

    private final ObjectMapper objectMapper;
    private final EventValidator eventValidator;
    private final CorrelationValidator correlationValidator;
    private final SourceValidator sourceValidator;
    private final CustomerRecordService customerRecordService;

    public ServiceRequestEventProcessor(
            ObjectMapper objectMapper,
            EventValidator eventValidator,
            CorrelationValidator correlationValidator,
            SourceValidator sourceValidator,
            CustomerRecordService customerRecordService) {
        this.objectMapper = objectMapper;
        this.eventValidator = eventValidator;
        this.correlationValidator = correlationValidator;
        this.sourceValidator = sourceValidator;
        this.customerRecordService = customerRecordService;
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
                    .log("Correlation header does not match event body - skipping database write");
            return;
        } catch (InvalidEventException | UnsupportedSourceException e) {
            log.atError()
                    .addKeyValue("event", "EVENT_VALIDATION_FAILED")
                    .addKeyValue("errorMessage", e.getMessage())
                    .log("Event failed validation - skipping database write");
            return;
        }

        log.atInfo().addKeyValue("event", "PAYLOAD_TRANSFORMED").log("Mapped event to customer record");

        customerRecordService.persist(event);

        long totalDurationMs = System.currentTimeMillis() - start;
        log.atInfo()
                .addKeyValue("event", "EVENT_PROCESSING_COMPLETED")
                .addKeyValue("durationMs", totalDurationMs)
                .log("Finished processing event");
    }
}
