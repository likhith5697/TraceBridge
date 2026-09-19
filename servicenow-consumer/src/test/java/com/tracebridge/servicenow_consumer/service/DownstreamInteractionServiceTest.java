package com.tracebridge.servicenow_consumer.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.tracebridge.servicenow_consumer.entity.DownstreamInteraction;
import com.tracebridge.servicenow_consumer.entity.DownstreamInteractionStatus;
import com.tracebridge.servicenow_consumer.repository.DownstreamInteractionRepository;
import com.tracebridge.servicenow_consumer.servicenow.PayloadSanitizer;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowIncidentRequest;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowResult;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import tools.jackson.databind.ObjectMapper;

class DownstreamInteractionServiceTest {

    private final DownstreamInteractionRepository repository = mock(DownstreamInteractionRepository.class);
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final PayloadSanitizer payloadSanitizer = new PayloadSanitizer(objectMapper);
    private final DownstreamInteractionService service =
            new DownstreamInteractionService(repository, payloadSanitizer, objectMapper);

    @Test
    void persistsSuccessfulInteraction() {
        UUID correlationId = UUID.randomUUID();
        ServiceNowIncidentRequest request = new ServiceNowIncidentRequest("short", "full", "1", "1", "network");
        ServiceNowResult result = ServiceNowResult.success(201, "abc123", "INC0012345", "{\"result\":{}}", 150);
        when(repository.save(any())).thenAnswer(invocation -> invocation.getArgument(0));

        service.record(correlationId, "/api/now/table/incident", request, result, Instant.now());

        ArgumentCaptor<DownstreamInteraction> captor = ArgumentCaptor.forClass(DownstreamInteraction.class);
        verify(repository).save(captor.capture());
        DownstreamInteraction saved = captor.getValue();

        assertThat(saved.getCorrelationId()).isEqualTo(correlationId);
        assertThat(saved.getTargetSystem()).isEqualTo("SERVICENOW");
        assertThat(saved.getOperation()).isEqualTo("CREATE_INCIDENT");
        assertThat(saved.getStatus()).isEqualTo(DownstreamInteractionStatus.SUCCESS);
        assertThat(saved.getHttpStatus()).isEqualTo(201);
        assertThat(saved.getAttemptNumber()).isEqualTo(1);
        assertThat(saved.getRequestPayload()).contains("short");
    }

    @Test
    void persistsFailedInteractionWithoutHttpStatus() {
        UUID correlationId = UUID.randomUUID();
        ServiceNowIncidentRequest request = new ServiceNowIncidentRequest("short", "full", "1", "1", "network");
        ServiceNowResult result = ServiceNowResult.failure(null, "TIMEOUT", "read timed out", null, 5000);
        when(repository.save(any())).thenAnswer(invocation -> invocation.getArgument(0));

        service.record(correlationId, "/api/now/table/incident", request, result, Instant.now());

        ArgumentCaptor<DownstreamInteraction> captor = ArgumentCaptor.forClass(DownstreamInteraction.class);
        verify(repository).save(captor.capture());
        DownstreamInteraction saved = captor.getValue();

        assertThat(saved.getStatus()).isEqualTo(DownstreamInteractionStatus.FAILED);
        assertThat(saved.getHttpStatus()).isNull();
        assertThat(saved.getErrorCode()).isEqualTo("TIMEOUT");
        assertThat(saved.getErrorMessage()).isEqualTo("read timed out");
    }

    @Test
    void redactsSensitiveFieldsInPersistedPayload() {
        UUID correlationId = UUID.randomUUID();
        ServiceNowIncidentRequest request = new ServiceNowIncidentRequest("short", "full", "1", "1", "network");
        String responseWithSecret = "{\"result\":{\"sys_id\":\"abc\"},\"authorization\":\"Basic xyz\"}";
        ServiceNowResult result = ServiceNowResult.success(201, "abc", "INC001", responseWithSecret, 100);
        when(repository.save(any())).thenAnswer(invocation -> invocation.getArgument(0));

        service.record(correlationId, "/api/now/table/incident", request, result, Instant.now());

        ArgumentCaptor<DownstreamInteraction> captor = ArgumentCaptor.forClass(DownstreamInteraction.class);
        verify(repository).save(captor.capture());
        DownstreamInteraction saved = captor.getValue();

        assertThat(saved.getResponsePayload()).doesNotContain("Basic xyz");
        assertThat(saved.getResponsePayload()).contains("[REDACTED]");
    }
}
