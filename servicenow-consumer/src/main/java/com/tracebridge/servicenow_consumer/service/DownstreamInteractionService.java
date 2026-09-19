package com.tracebridge.servicenow_consumer.service;

import com.tracebridge.servicenow_consumer.entity.DownstreamInteraction;
import com.tracebridge.servicenow_consumer.entity.DownstreamInteractionStatus;
import com.tracebridge.servicenow_consumer.repository.DownstreamInteractionRepository;
import com.tracebridge.servicenow_consumer.servicenow.PayloadSanitizer;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowClient;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowIncidentRequest;
import com.tracebridge.servicenow_consumer.servicenow.ServiceNowResult;
import java.time.Instant;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
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

    public void record(
            UUID correlationId,
            String endpoint,
            ServiceNowIncidentRequest requestBody,
            ServiceNowResult result,
            Instant requestTimestamp) {
        String requestJson = payloadSanitizer.sanitize(objectMapper.writeValueAsString(requestBody));
        String responseJson = payloadSanitizer.sanitize(result.rawResponseBody());

        DownstreamInteraction interaction = new DownstreamInteraction(
                correlationId,
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

        repository.save(interaction);

        log.atInfo()
                .addKeyValue("event", "DOWNSTREAM_INTERACTION_PERSISTED")
                .addKeyValue("targetSystem", TARGET_SYSTEM)
                .addKeyValue("status", interaction.getStatus())
                .addKeyValue("httpStatus", result.httpStatus())
                .log("Persisted downstream interaction record");
    }
}
