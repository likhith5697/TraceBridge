package com.tracebridge.service_request_api.event;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.tracebridge.service_request_api.entity.OutboxEvent;
import com.tracebridge.service_request_api.repository.OutboxEventRepository;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeoutException;
import org.apache.kafka.clients.producer.RecordMetadata;
import org.apache.kafka.common.TopicPartition;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Pageable;

@ExtendWith(MockitoExtension.class)
class OutboxPublisherTest {

    @Mock
    private OutboxEventRepository repository;

    @Mock
    private ServiceRequestEventPublisher eventPublisher;

    // Built in @BeforeEach, not as a field initializer - see the same note
    // in OutboxEventServiceTest for why (Mockito injects @Mock fields after
    // the test instance is constructed, not before).
    private OutboxPublisher publisher;

    @BeforeEach
    void setUp() {
        publisher = new OutboxPublisher(repository, eventPublisher, 50);
    }

    private OutboxEvent pendingEvent() {
        return new OutboxEvent(UUID.randomUUID(), UUID.randomUUID(), "servicenow.service-request", "{\"x\":1}");
    }

    private RecordMetadata fakeMetadata() {
        return new RecordMetadata(new TopicPartition("servicenow.service-request", 0), 0, 0, 0L, 0, 0);
    }

    @Test
    void marksAnEventSentOnSuccessfulPublish() throws Exception {
        OutboxEvent event = pendingEvent();
        when(repository.findBySentFalseOrderByCreatedAtAsc(any(Pageable.class))).thenReturn(List.of(event));
        when(eventPublisher.publish(anyString(), anyString(), anyString())).thenReturn(fakeMetadata());

        publisher.publishPendingEvents();

        ArgumentCaptor<OutboxEvent> captor = ArgumentCaptor.forClass(OutboxEvent.class);
        verify(repository).save(captor.capture());
        assertThat(captor.getValue().isSent()).isTrue();
        assertThat(captor.getValue().getSentAt()).isNotNull();
    }

    @Test
    void leavesAnEventUnsentAndRecordsTheErrorWhenPublishFails() throws Exception {
        OutboxEvent event = pendingEvent();
        when(repository.findBySentFalseOrderByCreatedAtAsc(any(Pageable.class))).thenReturn(List.of(event));
        when(eventPublisher.publish(anyString(), anyString(), anyString()))
                .thenThrow(new TimeoutException("Kafka did not respond in time"));

        publisher.publishPendingEvents();

        ArgumentCaptor<OutboxEvent> captor = ArgumentCaptor.forClass(OutboxEvent.class);
        verify(repository).save(captor.capture());
        assertThat(captor.getValue().isSent()).isFalse();
        assertThat(captor.getValue().getAttemptCount()).isEqualTo(1);
        assertThat(captor.getValue().getLastError()).contains("Kafka did not respond in time");
    }

    @Test
    void oneFailingRowDoesNotStopTheRestOfTheBatch() throws Exception {
        OutboxEvent willFail = pendingEvent();
        OutboxEvent willSucceed = pendingEvent();
        when(repository.findBySentFalseOrderByCreatedAtAsc(any(Pageable.class)))
                .thenReturn(List.of(willFail, willSucceed));
        when(eventPublisher.publish(anyString(), eq(willFail.getCorrelationId().toString()), anyString()))
                .thenThrow(new TimeoutException("down"));
        when(eventPublisher.publish(anyString(), eq(willSucceed.getCorrelationId().toString()), anyString()))
                .thenReturn(fakeMetadata());

        publisher.publishPendingEvents();

        assertThat(willFail.isSent()).isFalse();
        assertThat(willSucceed.isSent()).isTrue();
    }

    @Test
    void asksForNoMoreThanTheConfiguredBatchSize() {
        OutboxPublisher smallBatchPublisher = new OutboxPublisher(repository, eventPublisher, 7);
        when(repository.findBySentFalseOrderByCreatedAtAsc(any(Pageable.class))).thenReturn(List.of());

        smallBatchPublisher.publishPendingEvents();

        ArgumentCaptor<Pageable> pageableCaptor = ArgumentCaptor.forClass(Pageable.class);
        verify(repository).findBySentFalseOrderByCreatedAtAsc(pageableCaptor.capture());
        assertThat(pageableCaptor.getValue().getPageSize()).isEqualTo(7);
    }
}
