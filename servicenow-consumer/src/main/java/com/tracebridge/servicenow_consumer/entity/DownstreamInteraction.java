package com.tracebridge.servicenow_consumer.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "downstream_interaction", schema = "servicenow_consumer")
@Getter
@Setter
@NoArgsConstructor
public class DownstreamInteraction {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "correlation_id", nullable = false)
    private UUID correlationId;

    @Column(name = "target_system", nullable = false, length = 50)
    private String targetSystem;

    @Column(nullable = false, length = 50)
    private String operation;

    @Column(name = "http_method", nullable = false, length = 10)
    private String httpMethod;

    @Column(nullable = false, length = 500)
    private String endpoint;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "request_payload", columnDefinition = "jsonb")
    private String requestPayload;

    @Column(name = "request_timestamp", nullable = false)
    private Instant requestTimestamp;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "response_payload", columnDefinition = "jsonb")
    private String responsePayload;

    @Column(name = "response_timestamp")
    private Instant responseTimestamp;

    @Column(name = "http_status")
    private Integer httpStatus;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private DownstreamInteractionStatus status;

    @Column(name = "error_code", length = 100)
    private String errorCode;

    @Column(name = "error_message", length = 2000)
    private String errorMessage;

    @Column(name = "duration_ms", nullable = false)
    private long durationMs;

    @Column(name = "attempt_number", nullable = false)
    private int attemptNumber;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    public DownstreamInteraction(
            UUID correlationId,
            String targetSystem,
            String operation,
            String httpMethod,
            String endpoint,
            String requestPayload,
            Instant requestTimestamp,
            String responsePayload,
            Instant responseTimestamp,
            Integer httpStatus,
            DownstreamInteractionStatus status,
            String errorCode,
            String errorMessage,
            long durationMs,
            int attemptNumber) {
        this.correlationId = correlationId;
        this.targetSystem = targetSystem;
        this.operation = operation;
        this.httpMethod = httpMethod;
        this.endpoint = endpoint;
        this.requestPayload = requestPayload;
        this.requestTimestamp = requestTimestamp;
        this.responsePayload = responsePayload;
        this.responseTimestamp = responseTimestamp;
        this.httpStatus = httpStatus;
        this.status = status;
        this.errorCode = errorCode;
        this.errorMessage = errorMessage;
        this.durationMs = durationMs;
        this.attemptNumber = attemptNumber;
    }
}
