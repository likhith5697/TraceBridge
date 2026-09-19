package com.tracebridge.servicenow_consumer.exception;

public class InvalidEventException extends RuntimeException {

    public InvalidEventException(String message) {
        super(message);
    }
}
