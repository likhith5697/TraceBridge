package com.tracebridge.servicenow_consumer.consumer;

import com.tracebridge.servicenow_consumer.service.ServiceRequestEventProcessor;
import java.nio.charset.StandardCharsets;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.common.header.Header;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class ServiceRequestEventListener {

    private static final String CORRELATION_ID_HEADER = "X-Correlation-Id";

    private final ServiceRequestEventProcessor eventProcessor;

    public ServiceRequestEventListener(ServiceRequestEventProcessor eventProcessor) {
        this.eventProcessor = eventProcessor;
    }

    @KafkaListener(topics = "${tracebridge.kafka.topic.service-request-created}")
    public void onMessage(ConsumerRecord<String, String> record) {
        eventProcessor.process(record.value(), headerCorrelationId(record));
    }

    private String headerCorrelationId(ConsumerRecord<String, String> record) {
        Header header = record.headers().lastHeader(CORRELATION_ID_HEADER);
        return header != null ? new String(header.value(), StandardCharsets.UTF_8) : null;
    }
}
