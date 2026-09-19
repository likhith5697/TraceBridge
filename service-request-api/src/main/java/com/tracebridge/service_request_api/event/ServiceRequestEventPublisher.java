package com.tracebridge.service_request_api.event;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.clients.producer.RecordMetadata;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;

// The only place this service talks to Kafka. Deliberately dumb: it sends
// one already-serialized payload and either returns real proof of delivery
// (a partition + offset) or throws - it never decides what a failure means,
// that is OutboxPublisher's job (retry later). This class used to be called
// directly from the request-handling path and silently swallowed failures;
// it no longer catches anything, on purpose - see OutboxPublisher.
@Component
public class ServiceRequestEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(ServiceRequestEventPublisher.class);
    private static final String CORRELATION_ID_HEADER = "X-Correlation-Id";
    private static final long SEND_TIMEOUT_SECONDS = 5;

    private final KafkaTemplate<String, String> kafkaTemplate;

    public ServiceRequestEventPublisher(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public RecordMetadata publish(String topic, String correlationId, String payload)
            throws InterruptedException, ExecutionException, TimeoutException {
        log.atInfo().addKeyValue("event", "KAFKA_PUBLISH_STARTED").log("Sending event to Kafka");

        long start = System.currentTimeMillis();
        ProducerRecord<String, String> record = new ProducerRecord<>(topic, correlationId, payload);
        record.headers().add(CORRELATION_ID_HEADER, correlationId.getBytes(StandardCharsets.UTF_8));

        SendResult<String, String> result = kafkaTemplate.send(record).get(SEND_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        RecordMetadata metadata = result.getRecordMetadata();
        long durationMs = System.currentTimeMillis() - start;

        log.atInfo()
                .addKeyValue("event", "KAFKA_PUBLISHED")
                .addKeyValue("durationMs", durationMs)
                .log("Published event to Kafka (partition={}, offset={})", metadata.partition(), metadata.offset());

        return metadata;
    }
}
