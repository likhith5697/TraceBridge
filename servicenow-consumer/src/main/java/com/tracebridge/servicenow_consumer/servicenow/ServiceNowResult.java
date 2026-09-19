package com.tracebridge.servicenow_consumer.servicenow;

public record ServiceNowResult(
        boolean success,
        Integer httpStatus,
        String sysId,
        String number,
        String errorCode,
        String errorMessage,
        String rawResponseBody,
        long durationMs) {

    public static ServiceNowResult success(int httpStatus, String sysId, String number, String rawResponseBody, long durationMs) {
        return new ServiceNowResult(true, httpStatus, sysId, number, null, null, rawResponseBody, durationMs);
    }

    public static ServiceNowResult failure(
            Integer httpStatus, String errorCode, String errorMessage, String rawResponseBody, long durationMs) {
        return new ServiceNowResult(false, httpStatus, null, null, errorCode, errorMessage, rawResponseBody, durationMs);
    }

    public static ServiceNowResult notConfigured(long durationMs) {
        return failure(null, "NOT_CONFIGURED", "ServiceNow base URL is not configured", null, durationMs);
    }
}
