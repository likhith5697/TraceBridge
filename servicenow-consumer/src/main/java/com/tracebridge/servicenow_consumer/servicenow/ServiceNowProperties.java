package com.tracebridge.servicenow_consumer.servicenow;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "servicenow")
public record ServiceNowProperties(
        String baseUrl, String username, String password, long connectTimeoutMs, long readTimeoutMs) {

    public boolean isConfigured() {
        return baseUrl != null && !baseUrl.isBlank();
    }
}
