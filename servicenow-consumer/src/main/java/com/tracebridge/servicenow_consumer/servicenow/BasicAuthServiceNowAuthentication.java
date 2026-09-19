package com.tracebridge.servicenow_consumer.servicenow;

import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;

@Component
public class BasicAuthServiceNowAuthentication implements ServiceNowAuthentication {

    private final ServiceNowProperties properties;

    public BasicAuthServiceNowAuthentication(ServiceNowProperties properties) {
        this.properties = properties;
    }

    @Override
    public void apply(HttpHeaders headers) {
        headers.setBasicAuth(properties.username(), properties.password());
    }
}
