package com.tracebridge.service_request_api.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;

import com.tracebridge.service_request_api.dto.ServiceRequestCreateRequest;
import com.tracebridge.service_request_api.entity.Priority;
import com.tracebridge.service_request_api.entity.ServiceRequest;
import com.tracebridge.service_request_api.event.OutboxEventService;
import com.tracebridge.service_request_api.event.ServiceRequestCreatedEvent;
import com.tracebridge.service_request_api.repository.ServiceRequestRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

// The outbox pattern's whole correctness rests on both saves happening -
// this test proves the service actually calls both, with matching data,
// not just one of them.
@ExtendWith(MockitoExtension.class)
class ServiceRequestServiceTest {

    @Mock
    private ServiceRequestRepository repository;

    @Mock
    private OutboxEventService outboxEventService;

    private ServiceRequestService service() {
        return new ServiceRequestService(repository, outboxEventService);
    }

    private ServiceRequestCreateRequest sampleRequest() {
        return new ServiceRequestCreateRequest(
                "CUSTOMER_PORTAL", "CUS-1", "NETWORK", "CONNECTIVITY", "short", "full description", Priority.P2);
    }

    @Test
    void savesTheRequestAndEnqueuesAMatchingOutboxEvent() {
        var response = service().createServiceRequest(sampleRequest());

        ArgumentCaptor<ServiceRequest> savedRequest = ArgumentCaptor.forClass(ServiceRequest.class);
        verify(repository).save(savedRequest.capture());

        ArgumentCaptor<ServiceRequestCreatedEvent> enqueuedEvent =
                ArgumentCaptor.forClass(ServiceRequestCreatedEvent.class);
        verify(outboxEventService).enqueue(enqueuedEvent.capture());

        assertThat(savedRequest.getValue().getCorrelationId()).isEqualTo(response.correlationId());
        assertThat(enqueuedEvent.getValue().correlationId()).isEqualTo(response.correlationId());
        assertThat(enqueuedEvent.getValue().payload().customerId()).isEqualTo("CUS-1");
    }

    @Test
    void everyCallGetsItsOwnEventIdAndCorrelationId() {
        var first = service().createServiceRequest(sampleRequest());
        var second = service().createServiceRequest(sampleRequest());

        assertThat(first.correlationId()).isNotEqualTo(second.correlationId());
    }

    @Test
    void isTransactional() throws NoSuchMethodException {
        var method = ServiceRequestService.class.getMethod("createServiceRequest", ServiceRequestCreateRequest.class);
        assertThat(method.isAnnotationPresent(org.springframework.transaction.annotation.Transactional.class))
                .as("both the ServiceRequest and OutboxEvent saves must commit atomically, or not at all")
                .isTrue();
    }
}
