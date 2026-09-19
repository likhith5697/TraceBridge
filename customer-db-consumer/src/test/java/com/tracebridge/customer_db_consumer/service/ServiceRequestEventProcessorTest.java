package com.tracebridge.customer_db_consumer.service;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import com.tracebridge.customer_db_consumer.validation.CorrelationValidator;
import com.tracebridge.customer_db_consumer.validation.EventValidator;
import com.tracebridge.customer_db_consumer.validation.SourceValidator;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.json.JsonMapper;

@ExtendWith(MockitoExtension.class)
class ServiceRequestEventProcessorTest {

    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    @Mock
    private CustomerRecordService customerRecordService;

    private ServiceRequestEventProcessor processor() {
        return new ServiceRequestEventProcessor(
                objectMapper,
                new EventValidator(),
                new CorrelationValidator(),
                new SourceValidator(java.util.List.of("CUSTOMER_PORTAL")),
                customerRecordService);
    }

    private String validEventJson(UUID correlationId) {
        return """
                {
                  "eventId": "%s",
                  "eventType": "SERVICE_REQUEST_CREATED",
                  "eventVersion": 1,
                  "occurredAt": "%s",
                  "correlationId": "%s",
                  "source": "CUSTOMER_PORTAL",
                  "payload": {
                    "customerId": "cust-1",
                    "category": "billing",
                    "subcategory": "invoice",
                    "shortDescription": "short",
                    "description": "long",
                    "priority": "P2"
                  }
                }
                """.formatted(UUID.randomUUID(), Instant.now(), correlationId);
    }

    @Test
    void valid_event_reaches_customer_record_service() {
        UUID correlationId = UUID.randomUUID();

        processor().process(validEventJson(correlationId), correlationId.toString());

        verify(customerRecordService).persist(any());
    }

    @Test
    void malformed_json_is_discarded_without_touching_the_database() {
        processor().process("not valid json", "irrelevant");

        verify(customerRecordService, never()).persist(any());
    }

    @Test
    void correlation_mismatch_skips_the_database_write() {
        UUID correlationId = UUID.randomUUID();

        processor().process(validEventJson(correlationId), UUID.randomUUID().toString());

        verify(customerRecordService, never()).persist(any());
    }

    @Test
    void missing_correlation_header_skips_the_database_write() {
        UUID correlationId = UUID.randomUUID();

        processor().process(validEventJson(correlationId), null);

        verify(customerRecordService, never()).persist(any());
    }
}
