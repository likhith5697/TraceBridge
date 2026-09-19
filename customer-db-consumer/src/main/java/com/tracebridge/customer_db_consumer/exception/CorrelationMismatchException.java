package com.tracebridge.customer_db_consumer.exception;

public class CorrelationMismatchException extends RuntimeException {

    public CorrelationMismatchException(String message) {
        super(message);
    }
}
