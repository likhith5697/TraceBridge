package com.tracebridge.servicenow_consumer.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowClient;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowIncidentMapper;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowResult;
import com.tracebridge.servicenow_consumer.validation.CorrelationValidator;
import com.tracebridge.servicenow_consumer.validation.EventValidator;
import com.tracebridge.servicenow_consumer.validation.SourceValidator;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import tools.jackson.databind.ObjectMapper;

// Verifies the two properties that matter most for observability: correlationId/eventId are
// attached to every log line for a record via MDC, and MDC never leaks into the next record
// processed on the same (reused) Kafka consumer thread.
class ServiceRequestEventProcessorLoggingTest {

    private static final String DUMMY_SECRET = "supersecretpassword";

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ServiceNowClient serviceNowClient = mock(ServiceNowClient.class);
    private final DownstreamInteractionService downstreamInteractionService = mock(DownstreamInteractionService.class);
    private final ServiceRequestEventProcessor processor = new ServiceRequestEventProcessor(
            objectMapper,
            new EventValidator(),
            new CorrelationValidator(),
            new SourceValidator(List.of("CUSTOMER_PORTAL")),
            new ServiceNowIncidentMapper(),
            serviceNowClient,
            downstreamInteractionService);

    private Logger rootLogger;
    private ListAppender<ILoggingEvent> appender;

    @BeforeEach
    void setUp() {
        rootLogger = (Logger) LoggerFactory.getLogger(Logger.ROOT_LOGGER_NAME);
        appender = new ListAppender<>();
        appender.start();
        rootLogger.addAppender(appender);
    }

    @AfterEach
    void tearDown() {
        rootLogger.detachAppender(appender);
        MDC.clear();
    }

    private String eventJson(UUID correlationId) {
        return """
                {
                  "eventId": "%s",
                  "eventType": "SERVICE_REQUEST_CREATED",
                  "eventVersion": 1,
                  "occurredAt": "%s",
                  "correlationId": "%s",
                  "source": "CUSTOMER_PORTAL",
                  "payload": {
                    "customerId": "CUS-1",
                    "category": "NETWORK",
                    "subcategory": "CONNECTIVITY",
                    "shortDescription": "short",
                    "description": "full",
                    "priority": "P2"
                  }
                }
                """
                .formatted(UUID.randomUUID(), Instant.now(), correlationId);
    }

    @Test
    void attachesCorrelationIdToEveryLogLineAndClearsMdcAfterward() {
        UUID correlationId = UUID.randomUUID();
        when(serviceNowClient.endpoint()).thenReturn("/api/now/table/incident");
        when(serviceNowClient.createIncident(any(), anyString()))
                .thenReturn(ServiceNowResult.success(201, "sys1", "INC0001", "{}", 10));

        processor.process(eventJson(correlationId), correlationId.toString());

        List<ILoggingEvent> events = appender.list;
        assertThat(events).isNotEmpty();
        for (ILoggingEvent event : events) {
            assertThat(event.getMDCPropertyMap()).containsEntry("correlationId", correlationId.toString());
        }
        assertThat(MDC.get("correlationId")).isNull();
        assertThat(MDC.get("eventId")).isNull();
    }

    @Test
    void doesNotLeakCorrelationIdIntoTheNextRecordOnTheSameThread() {
        UUID firstCorrelationId = UUID.randomUUID();
        when(serviceNowClient.endpoint()).thenReturn("/api/now/table/incident");
        when(serviceNowClient.createIncident(any(), anyString()))
                .thenReturn(ServiceNowResult.success(201, "sys1", "INC0001", "{}", 10));

        processor.process(eventJson(firstCorrelationId), firstCorrelationId.toString());
        appender.list.clear();

        // Simulate the same (reused) consumer thread immediately picking up a malformed record.
        processor.process("not valid json", UUID.randomUUID().toString());

        for (ILoggingEvent event : appender.list) {
            assertThat(event.getMDCPropertyMap()).doesNotContainValue(firstCorrelationId.toString());
        }
    }

    @Test
    void neverLogsSecretLookingValues() {
        UUID correlationId = UUID.randomUUID();
        when(serviceNowClient.endpoint()).thenReturn("/api/now/table/incident");
        when(serviceNowClient.createIncident(any(), anyString()))
                .thenReturn(ServiceNowResult.failure(401, "UNAUTHORIZED", DUMMY_SECRET, null, 5));

        processor.process(eventJson(correlationId), correlationId.toString());

        for (ILoggingEvent event : appender.list) {
            assertThat(event.getFormattedMessage()).doesNotContain(DUMMY_SECRET);
            if (event.getKeyValuePairs() != null) {
                event.getKeyValuePairs()
                        .forEach(kv -> assertThat(String.valueOf(kv.value)).doesNotContain(DUMMY_SECRET));
            }
        }
    }
}
