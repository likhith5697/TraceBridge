package com.tracebridge.customer_db_consumer.entity;

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

// The actual business write this consumer is responsible for. There is
// deliberately no outcome/status column here the way servicenow-consumer's
// DownstreamInteraction has one: a row only ever exists here on success -
// see the module-level comment in V1__create_customer_record_table.sql for
// why a failure can't be safely recorded in this same database.
@Entity
@Table(name = "customer_record", schema = "customer_db_consumer")
@Getter
@Setter
@NoArgsConstructor
public class CustomerRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "correlation_id", nullable = false)
    private UUID correlationId;

    // Idempotency key: unique per event, stable across Kafka redeliveries -
    // see V2__add_event_id_for_idempotency.sql for why.
    @Column(name = "event_id")
    private UUID eventId;

    @Column(name = "customer_id", nullable = false, length = 100)
    private String customerId;

    @Column(nullable = false, length = 100)
    private String category;

    @Column(nullable = false, length = 100)
    private String subcategory;

    @Column(name = "short_description", nullable = false, length = 500)
    private String shortDescription;

    @Column(nullable = false, length = 20)
    private String priority;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    public CustomerRecord(
            UUID correlationId, UUID eventId, String customerId, String category, String subcategory,
            String shortDescription, String priority) {
        this.correlationId = correlationId;
        this.eventId = eventId;
        this.customerId = customerId;
        this.category = category;
        this.subcategory = subcategory;
        this.shortDescription = shortDescription;
        this.priority = priority;
    }
}
