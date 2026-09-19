package com.tracebridge.customer_db_consumer.validation;

import com.tracebridge.customer_db_consumer.exception.CorrelationMismatchException;
import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
public class CorrelationValidator {

    public void validate(UUID bodyCorrelationId, String headerCorrelationId) {
        if (headerCorrelationId == null || headerCorrelationId.isBlank()) {
            throw new CorrelationMismatchException(
                    "X-Correlation-Id header is missing, body correlationId=" + bodyCorrelationId);
        }

        UUID headerId;
        try {
            headerId = UUID.fromString(headerCorrelationId);
        } catch (IllegalArgumentException e) {
            throw new CorrelationMismatchException(
                    "X-Correlation-Id header is not a valid UUID: " + headerCorrelationId);
        }

        if (!headerId.equals(bodyCorrelationId)) {
            throw new CorrelationMismatchException(
                    "body correlationId=" + bodyCorrelationId + " does not match header correlationId=" + headerId);
        }
    }
}
