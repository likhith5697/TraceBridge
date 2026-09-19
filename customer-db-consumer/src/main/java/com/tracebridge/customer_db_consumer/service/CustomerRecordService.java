package com.tracebridge.customer_db_consumer.service;

import com.tracebridge.customer_db_consumer.entity.CustomerRecord;
import com.tracebridge.customer_db_consumer.event.ServiceRequestCreatedEvent;
import com.tracebridge.customer_db_consumer.repository.CustomerRecordRepository;
import java.util.Locale;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;

// The actual downstream dependency call this whole consumer exists to make -
// a real JDBC write to customer-postgres, the Phase 8 controlled dependency.
//
// Unlike servicenow-consumer's DownstreamInteractionService, there is no
// separate "record the outcome" step: the dependency being tested here IS
// this same Postgres, so a write failure cannot be durably recorded in it -
// there is nowhere safe to persist "the database write failed" when the
// database is what failed. That failure is only ever observable through the
// structured log line below (DB_OPERATION_FAILED), which flows to OpenSearch
// exactly like every other TraceBridge log line and is what search_logs /
// get_transaction_timeline surface to the investigator.
@Service
public class CustomerRecordService {

    private static final Logger log = LoggerFactory.getLogger(CustomerRecordService.class);
    private static final String TARGET_SYSTEM = "CUSTOMER_POSTGRES";

    private final CustomerRecordRepository repository;

    public CustomerRecordService(CustomerRecordRepository repository) {
        this.repository = repository;
    }

    // The idempotency check: called BEFORE attempting the write, so a Kafka
    // redelivery of an event that already succeeded never creates a second
    // customer_record row. A redelivery of an event whose first attempt
    // FAILED correctly falls through and retries - see this class's Javadoc
    // and V2's migration comment for why that asymmetry is intentional.
    public boolean alreadyProcessed(UUID eventId) {
        return eventId != null && repository.existsByEventId(eventId);
    }

    public void persist(ServiceRequestCreatedEvent event) {
        long start = System.currentTimeMillis();
        log.atInfo()
                .addKeyValue("event", "DB_OPERATION_STARTED")
                .addKeyValue("targetSystem", TARGET_SYSTEM)
                .log("Persisting customer record");

        try {
            CustomerRecord record = new CustomerRecord(
                    event.correlationId(),
                    event.eventId(),
                    event.payload().customerId(),
                    event.payload().category(),
                    event.payload().subcategory(),
                    event.payload().shortDescription(),
                    event.payload().priority().name());
            repository.save(record);

            long duration = System.currentTimeMillis() - start;
            log.atInfo()
                    .addKeyValue("event", "DB_OPERATION_SUCCEEDED")
                    .addKeyValue("targetSystem", TARGET_SYSTEM)
                    .addKeyValue("status", "SUCCESS")
                    .addKeyValue("durationMs", duration)
                    .log("Customer record write succeeded");
            log.atInfo()
                    .addKeyValue("event", "CUSTOMER_RECORD_PERSISTED")
                    .addKeyValue("targetSystem", TARGET_SYSTEM)
                    .log("Persisted customer record");
        } catch (DataIntegrityViolationException e) {
            // Belt-and-suspenders: alreadyProcessed() closes this window for
            // the normal case: a genuine race (two threads processing the
            // same eventId at once) is only prevented for certain by the
            // database's own unique constraint. Logged, not thrown.
            log.atWarn()
                    .addKeyValue("event", "DUPLICATE_EVENT_DETECTED_ON_INSERT")
                    .addKeyValue("targetSystem", TARGET_SYSTEM)
                    .log("A customer_record row for this eventId already exists - discarding the duplicate insert");
        } catch (RuntimeException e) {
            // Deliberately broad, not just org.springframework.dao.DataAccessException:
            // a connection that cannot be acquired at all to even BEGIN the
            // transaction (exactly what happens when customer-postgres is down)
            // surfaces as org.springframework.transaction.CannotCreateTransactionException,
            // a completely separate hierarchy from DataAccessException. This
            // boundary's whole job is to absorb every downstream-database
            // failure mode into a log line and never let it escape to Kafka's
            // listener error handling, which would otherwise redeliver the
            // same record forever - mirroring how ServiceNowClient.createIncident
            // never throws at all.
            long duration = System.currentTimeMillis() - start;
            String rootMessage = rootMessage(e);
            String errorCode = classify(rootMessage);
            log.atError()
                    .addKeyValue("event", "DB_OPERATION_FAILED")
                    .addKeyValue("targetSystem", TARGET_SYSTEM)
                    .addKeyValue("status", "FAILED")
                    .addKeyValue("errorCode", errorCode)
                    .addKeyValue("durationMs", duration)
                    .log("Customer record write failed: {}", rootMessage);
        }
    }

    private String classify(String message) {
        String lower = message.toLowerCase(Locale.ROOT);
        if (lower.contains("timeout") || lower.contains("timed out")) {
            return "TIMEOUT";
        }
        if (lower.contains("refused")) {
            return "CONNECTION_REFUSED";
        }
        return "DATABASE_ERROR";
    }

    private String rootMessage(Throwable e) {
        Throwable cause = e;
        while (cause.getCause() != null) {
            cause = cause.getCause();
        }
        return cause.getMessage() != null ? cause.getMessage() : e.getMessage();
    }
}
