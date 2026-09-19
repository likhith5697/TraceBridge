package com.tracebridge.service_request_api.event;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.clients.producer.RecordMetadata;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Component
public class ServiceRequestEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(ServiceRequestEventPublisher.class);
    private static final String CORRELATION_ID_HEADER = "X-Correlation-Id";

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;
    private final String topic;

    public ServiceRequestEventPublisher(
            KafkaTemplate<String, String> kafkaTemplate,
            ObjectMapper objectMapper,
            @Value("${tracebridge.kafka.topic.service-request-created}") String topic) {
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
        this.topic = topic;
    }

    public void publish(ServiceRequestCreatedEvent event) {
        String correlationId = event.correlationId().toString();

        log.atInfo().addKeyValue("event", "KAFKA_PUBLISH_STARTED").log("Sending event to Kafka");

        long start = System.currentTimeMillis();
        try {
            String payload = objectMapper.writeValueAsString(event);

            ProducerRecord<String, String> record = new ProducerRecord<>(topic, correlationId, payload);
            record.headers().add(CORRELATION_ID_HEADER, correlationId.getBytes(StandardCharsets.UTF_8));

            SendResult<String, String> result = kafkaTemplate.send(record).get(5, TimeUnit.SECONDS);
            RecordMetadata metadata = result.getRecordMetadata();
            long durationMs = System.currentTimeMillis() - start;

            log.atInfo()
                    .addKeyValue("event", "KAFKA_PUBLISHED")
                    .addKeyValue("durationMs", durationMs)
                    .log("Published event to Kafka (partition={}, offset={})", metadata.partition(), metadata.offset());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            logPublishFailure(start, e.getMessage());
        } catch (ExecutionException | TimeoutException | JacksonException e) {
            logPublishFailure(start, e.getMessage());
        }
    }

    private void logPublishFailure(long start, String reason) {
        long durationMs = System.currentTimeMillis() - start;
        log.atError()
                .addKeyValue("event", "KAFKA_PUBLISH_FAILED")
                .addKeyValue("errorMessage", reason)
                .addKeyValue("durationMs", durationMs)
                .log("Failed to publish event to Kafka");
    }
}
