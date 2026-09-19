package com.tracebridge.servicenow_consumer.validation;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.tracebridge.servicenow_consumer.exception.UnsupportedSourceException;
import java.util.List;
import org.junit.jupiter.api.Test;

class SourceValidatorTest {

    private final SourceValidator validator = new SourceValidator(List.of("CUSTOMER_PORTAL"));

    @Test
    void acceptsKnownSource() {
        assertThatCode(() -> validator.validate("CUSTOMER_PORTAL")).doesNotThrowAnyException();
    }

    @Test
    void rejectsUnknownSource() {
        assertThatThrownBy(() -> validator.validate("SOME_OTHER_SYSTEM"))
                .isInstanceOf(UnsupportedSourceException.class);
    }
}
