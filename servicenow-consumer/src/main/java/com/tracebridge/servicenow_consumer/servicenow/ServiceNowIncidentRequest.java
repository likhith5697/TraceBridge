package com.tracebridge.servicenow_consumer.servicenow;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ServiceNowIncidentRequest(
        @JsonProperty("short_description") String shortDescription,
        String description,
        String urgency,
        String impact,
        String category) {}
