package com.tracebridge.servicenow_consumer.servicenow;

import org.springframework.http.HttpHeaders;

public interface ServiceNowAuthentication {

    void apply(HttpHeaders headers);
}
