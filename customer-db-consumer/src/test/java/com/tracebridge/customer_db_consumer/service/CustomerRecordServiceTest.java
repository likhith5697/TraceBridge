package com.tracebridge.customer_db_consumer.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.tracebridge.customer_db_consumer.entity.CustomerRecord;
import com.tracebridge.customer_db_consumer.event.Priority;
import com.tracebridge.customer_db_consumer.event.ServiceRequestCreatedEvent;
import com.tracebridge.customer_db_consumer.repository.CustomerRecordRepository;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.TransientDataAccessResourceException;
import org.springframework.transaction.CannotCreateTransactionException;

@ExtendWith(MockitoExtension.class)
class CustomerRecordServiceTest {

    @Mock
    private CustomerRecordRepository repository;

    private ServiceRequestCreatedEvent event() {
        return new ServiceRequestCreatedEvent(
                UUID.randomUUID(),
                ServiceRequestCreatedEvent.SUPPORTED_EVENT_TYPE,
                ServiceRequestCreatedEvent.SUPPORTED_EVENT_VERSION,
                Instant.now(),
                UUID.randomUUID(),
                "CUSTOMER_PORTAL",
                new ServiceRequestCreatedEvent.Payload(
                        "cust-1", "billing", "invoice", "short desc", "long desc", Priority.P2));
    }

    @Test
    void persists_a_real_record_on_success() {
        CustomerRecordService service = new CustomerRecordService(repository);

        service.persist(event());

        verify(repository).save(any(CustomerRecord.class));
    }

    @Test
    void a_connection_refused_failure_is_caught_and_never_propagates() {
        CustomerRecordService service = new CustomerRecordService(repository);
        when(repository.save(any())).thenThrow(
                new DataAccessResourceFailureException("Connection refused: connect"));

        assertThatCode(() -> service.persist(event())).doesNotThrowAnyException();
    }

    @Test
    void a_transient_timeout_failure_is_also_caught_and_never_propagates() {
        CustomerRecordService service = new CustomerRecordService(repository);
        when(repository.save(any())).thenThrow(
                new TransientDataAccessResourceException("Connection is not available, timeout waiting for connection"));

        assertThatCode(() -> service.persist(event())).doesNotThrowAnyException();
    }

    @Test
    void a_connection_that_cannot_even_be_acquired_is_caught_and_never_propagates() {
        // This is the exception a stopped customer-postgres actually produces in
        // practice: CannotCreateTransactionException is NOT a DataAccessException
        // subtype (it is org.springframework.transaction.TransactionException), so
        // a narrower catch here would let it slip through uncaught into the Kafka
        // listener - which is exactly what a live run against a real stopped
        // dependency caught: the same message got redelivered by Kafka forever
        // instead of ever logging DB_OPERATION_FAILED.
        CustomerRecordService service = new CustomerRecordService(repository);
        when(repository.save(any())).thenThrow(
                new CannotCreateTransactionException("Could not open JPA EntityManager for transaction"));

        assertThatCode(() -> service.persist(event())).doesNotThrowAnyException();
    }

    @Test
    void alreadyProcessedIsTrueOnlyWhenARowExistsForThatEventId() {
        CustomerRecordService service = new CustomerRecordService(repository);
        UUID knownEventId = UUID.randomUUID();
        UUID unknownEventId = UUID.randomUUID();
        when(repository.existsByEventId(knownEventId)).thenReturn(true);
        when(repository.existsByEventId(unknownEventId)).thenReturn(false);

        assertThat(service.alreadyProcessed(knownEventId)).isTrue();
        assertThat(service.alreadyProcessed(unknownEventId)).isFalse();
        assertThat(service.alreadyProcessed(null)).isFalse();
    }

    @Test
    void aDuplicateInsertRaceIsCaughtAndLoggedNotThrown() {
        CustomerRecordService service = new CustomerRecordService(repository);
        when(repository.save(any())).thenThrow(new DataIntegrityViolationException("duplicate key value"));

        assertThatCode(() -> service.persist(event())).doesNotThrowAnyException();
    }
}
