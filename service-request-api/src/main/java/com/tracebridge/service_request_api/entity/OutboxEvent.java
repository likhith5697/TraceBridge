package com.tracebridge.service_request_api.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
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

// One row per event that must reach Kafka. Written in the SAME transaction
// as the business row it accompanies (see ServiceRequestService) - that is
// the entire mechanism that makes "saved but never published" impossible.
// OutboxPublisher is the only thing that ever reads/updates this table.
@Entity
@Table(name = "outbox_event")
@Getter
@Setter
@NoArgsConstructor
public class OutboxEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "correlation_id", nullable = false)
    private UUID correlationId;

    // Also the consumer-side idempotency key once this reaches Kafka - see
    // servicenow-consumer/customer-db-consumer's V2 migrations. Unique here
    // too, so this table can never itself queue the same event twice.
    @Column(name = "event_id", nullable = false, unique = true)
    private UUID eventId;

    @Column(nullable = false, length = 200)
    private String topic;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String payload;

    @Column(nullable = false)
    private boolean sent;

    @Column(name = "attempt_count", nullable = false)
    private int attemptCount;

    @Column(name = "last_error", length = 2000)
    private String lastError;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "sent_at")
    private Instant sentAt;

    public OutboxEvent(UUID correlationId, UUID eventId, String topic, String payload) {
        this.correlationId = correlationId;
        this.eventId = eventId;
        this.topic = topic;
        this.payload = payload;
        this.sent = false;
        this.attemptCount = 0;
    }
}
