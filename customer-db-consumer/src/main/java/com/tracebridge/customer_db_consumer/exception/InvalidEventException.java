package com.tracebridge.customer_db_consumer.exception;

public class InvalidEventException extends RuntimeException {

    public InvalidEventException(String message) {
        super(message);
    }
}
