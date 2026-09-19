package com.tracebridge.servicenow_consumer.servicenow;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ServiceNowIncidentResponse(Result result) {

    public record Result(@JsonProperty("sys_id") String sysId, String number) {}
}
