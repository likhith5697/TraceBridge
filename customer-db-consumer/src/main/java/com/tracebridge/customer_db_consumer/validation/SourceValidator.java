package com.tracebridge.customer_db_consumer.validation;

import com.tracebridge.customer_db_consumer.exception.UnsupportedSourceException;
import java.util.List;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class SourceValidator {

    private final Set<String> supportedSources;

    public SourceValidator(
            @Value("${tracebridge.supported-sources:CUSTOMER_PORTAL}") List<String> supportedSources) {
        this.supportedSources = Set.copyOf(supportedSources);
    }

    public void validate(String source) {
        if (!supportedSources.contains(source)) {
            throw new UnsupportedSourceException("unsupported source: " + source);
        }
    }
}
