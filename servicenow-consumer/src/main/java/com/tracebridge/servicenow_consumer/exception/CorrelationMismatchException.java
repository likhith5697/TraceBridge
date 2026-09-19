package com.tracebridge.servicenow_consumer.exception;

public class CorrelationMismatchException extends RuntimeException {

    public CorrelationMismatchException(String message) {
        super(message);
    }
}
