package com.tracebridge.customer_db_consumer.validation;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.tracebridge.customer_db_consumer.exception.CorrelationMismatchException;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class CorrelationValidatorTest {

    private final CorrelationValidator validator = new CorrelationValidator();

    @Test
    void accepts_matching_header_and_body() {
        UUID id = UUID.randomUUID();
        assertThatCode(() -> validator.validate(id, id.toString())).doesNotThrowAnyException();
    }

    @Test
    void rejects_missing_header() {
        assertThatThrownBy(() -> validator.validate(UUID.randomUUID(), null))
                .isInstanceOf(CorrelationMismatchException.class);
    }

    @Test
    void rejects_header_that_does_not_match_body() {
        assertThatThrownBy(() -> validator.validate(UUID.randomUUID(), UUID.randomUUID().toString()))
                .isInstanceOf(CorrelationMismatchException.class);
    }

    @Test
    void rejects_header_that_is_not_a_valid_uuid() {
        assertThatThrownBy(() -> validator.validate(UUID.randomUUID(), "not-a-uuid"))
                .isInstanceOf(CorrelationMismatchException.class);
    }
}
