package com.tracebridge.servicenow_consumer.validation;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.tracebridge.servicenow_consumer.exception.CorrelationMismatchException;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class CorrelationValidatorTest {

    private final CorrelationValidator validator = new CorrelationValidator();

    @Test
    void acceptsMatchingCorrelationIds() {
        UUID id = UUID.randomUUID();
        assertThatCode(() -> validator.validate(id, id.toString())).doesNotThrowAnyException();
    }

    @Test
    void rejectsMismatchedCorrelationIds() {
        UUID bodyId = UUID.randomUUID();
        String headerId = UUID.randomUUID().toString();

        assertThatThrownBy(() -> validator.validate(bodyId, headerId))
                .isInstanceOf(CorrelationMismatchException.class);
    }

    @Test
    void rejectsMissingHeader() {
        UUID bodyId = UUID.randomUUID();

        assertThatThrownBy(() -> validator.validate(bodyId, null))
                .isInstanceOf(CorrelationMismatchException.class);
    }

    @Test
    void rejectsMalformedHeader() {
        UUID bodyId = UUID.randomUUID();

        assertThatThrownBy(() -> validator.validate(bodyId, "not-a-uuid"))
                .isInstanceOf(CorrelationMismatchException.class);
    }
}
