package com.tracebridge.servicenow_consumer.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.tracebridge.servicenow_consumer.servicenow.ServiceNowClient;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowIncidentMapper;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowResult;
import com.tracebridge.servicenow_consumer.validation.CorrelationValidator;
import com.tracebridge.servicenow_consumer.validation.EventValidator;
import com.tracebridge.servicenow_consumer.validation.SourceValidator;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

class ServiceRequestEventProcessorTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final EventValidator eventValidator = new EventValidator();
    private final CorrelationValidator correlationValidator = new CorrelationValidator();
    private final SourceValidator sourceValidator = new SourceValidator(List.of("CUSTOMER_PORTAL"));
    private final ServiceNowIncidentMapper incidentMapper = new ServiceNowIncidentMapper();
    private final ServiceNowClient serviceNowClient = mock(ServiceNowClient.class);
    private final DownstreamInteractionService downstreamInteractionService = mock(DownstreamInteractionService.class);

    private final ServiceRequestEventProcessor processor = new ServiceRequestEventProcessor(
            objectMapper,
            eventValidator,
            correlationValidator,
            sourceValidator,
            incidentMapper,
            serviceNowClient,
            downstreamInteractionService);

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
                    "customerId": "CUS-92831",
                    "category": "NETWORK",
                    "subcategory": "CONNECTIVITY",
                    "shortDescription": "Customer circuit unavailable",
                    "description": "Customer reports complete loss of connectivity",
                    "priority": "P2"
                  }
                }
                """
                .formatted(UUID.randomUUID(), Instant.now(), correlationId);
    }

    @Test
    void callsServiceNowAndPersistsWhenEventAndCorrelationAreValid() {
        UUID correlationId = UUID.randomUUID();
        when(serviceNowClient.endpoint()).thenReturn("/api/now/table/incident");
        when(serviceNowClient.createIncident(any(), anyString()))
                .thenReturn(ServiceNowResult.success(201, "sys1", "INC0001", "{}", 42));

        processor.process(eventJson(correlationId), correlationId.toString());

        verify(serviceNowClient).createIncident(any(), eq(correlationId.toString()));
        verify(downstreamInteractionService)
                .record(eq(correlationId), any(), anyString(), any(), any(), any(Instant.class));
    }

    @Test
    void skipsServiceNowWhenEventWasAlreadyProcessed() {
        UUID correlationId = UUID.randomUUID();
        when(downstreamInteractionService.alreadyProcessed(any())).thenReturn(true);

        processor.process(eventJson(correlationId), correlationId.toString());

        verify(serviceNowClient, never()).createIncident(any(), anyString());
        verify(downstreamInteractionService, never()).record(any(), any(), anyString(), any(), any(), any());
    }

    @Test
    void doesNotCallServiceNowWhenCorrelationIdsMismatch() {
        UUID bodyCorrelationId = UUID.randomUUID();
        UUID headerCorrelationId = UUID.randomUUID();

        processor.process(eventJson(bodyCorrelationId), headerCorrelationId.toString());

        verify(serviceNowClient, never()).createIncident(any(), anyString());
        verify(downstreamInteractionService, never()).record(any(), any(), anyString(), any(), any(), any());
    }

    @Test
    void doesNotCallServiceNowForUnsupportedSource() {
        UUID correlationId = UUID.randomUUID();
        String json = eventJson(correlationId).replace("CUSTOMER_PORTAL", "UNKNOWN_SYSTEM");

        processor.process(json, correlationId.toString());

        verify(serviceNowClient, never()).createIncident(any(), anyString());
        verify(downstreamInteractionService, never()).record(any(), any(), anyString(), any(), any(), any());
    }

    @Test
    void doesNotThrowOnMalformedJson() {
        assertThat(catchNothing(() -> processor.process("not json", UUID.randomUUID().toString()))).isTrue();
        verify(serviceNowClient, never()).createIncident(any(), anyString());
    }

    private boolean catchNothing(Runnable runnable) {
        runnable.run();
        return true;
    }
}
