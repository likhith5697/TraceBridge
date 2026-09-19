package com.tracebridge.service_request_api.event;

import com.tracebridge.service_request_api.entity.OutboxEvent;
import com.tracebridge.service_request_api.repository.OutboxEventRepository;
import java.time.Instant;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

// The only thing that ever reads outbox_event or calls Kafka on the producer
// side. Runs on a fixed timer, not in the request path - a request handler
// never waits on this. Each row is published and saved independently (one
// repository.save() per row is already its own atomic unit via Spring Data
// JPA - see the comment on that in ServiceRequestService) so one failing
// row's exception can never roll back another row's already-successful
// "sent = true" update from the same poll cycle.
@Component
public class OutboxPublisher {

    private static final Logger log = LoggerFactory.getLogger(OutboxPublisher.class);

    private final OutboxEventRepository repository;
    private final ServiceRequestEventPublisher eventPublisher;
    private final int batchSize;

    public OutboxPublisher(
            OutboxEventRepository repository,
            ServiceRequestEventPublisher eventPublisher,
            @Value("${tracebridge.outbox.batch-size:50}") int batchSize) {
        this.repository = repository;
        this.eventPublisher = eventPublisher;
        this.batchSize = batchSize;
    }

    @Scheduled(fixedDelayString = "${tracebridge.outbox.poll-interval-ms:1000}")
    public void publishPendingEvents() {
        List<OutboxEvent> pending = repository.findBySentFalseOrderByCreatedAtAsc(PageRequest.of(0, batchSize));
        for (OutboxEvent event : pending) {
            publishOne(event);
        }
    }

    private void publishOne(OutboxEvent event) {
        MDC.put("correlationId", event.getCorrelationId().toString());
        MDC.put("eventId", event.getEventId().toString());
        try {
            eventPublisher.publish(event.getTopic(), event.getCorrelationId().toString(), event.getPayload());

            event.setSent(true);
            event.setSentAt(Instant.now());
            event.setLastError(null);
            repository.save(event);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            recordFailure(event, e.getMessage());
        } catch (Exception e) {
            // Deliberately broad, not just ExecutionException/TimeoutException:
            // found live that Kafka's own client can throw an UNCHECKED
            // org.apache.kafka.common.errors.TimeoutException directly out of
            // send() itself (when it can't fetch topic metadata in time) -
            // a completely different class from java.util.concurrent.TimeoutException,
            // and easy to miss since both are named "TimeoutException". A
            // narrower catch here let it escape into Spring's scheduler, which
            // silently swallows it via its default error handler AND aborts
            // every remaining row in that poll cycle's batch - exactly the kind
            // of silent, batch-wide failure this whole pattern exists to avoid.
            recordFailure(event, e.getMessage());
        } finally {
            MDC.clear();
        }
    }

    private void recordFailure(OutboxEvent event, String reason) {
        event.setAttemptCount(event.getAttemptCount() + 1);
        event.setLastError(reason);
        repository.save(event);

        log.atWarn()
                .addKeyValue("event", "KAFKA_PUBLISH_FAILED")
                .addKeyValue("errorMessage", reason)
                .addKeyValue("attemptCount", event.getAttemptCount())
                .log("Failed to publish outbox event - will retry on the next poll");
    }
}
