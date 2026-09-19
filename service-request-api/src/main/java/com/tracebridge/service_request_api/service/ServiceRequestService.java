package com.tracebridge.service_request_api.service;

import com.tracebridge.service_request_api.dto.ServiceRequestCreateRequest;
import com.tracebridge.service_request_api.dto.ServiceRequestResponse;
import com.tracebridge.service_request_api.entity.RequestStatus;
import com.tracebridge.service_request_api.entity.ServiceRequest;
import com.tracebridge.service_request_api.event.OutboxEventService;
import com.tracebridge.service_request_api.event.ServiceRequestCreatedEvent;
import com.tracebridge.service_request_api.repository.ServiceRequestRepository;
import java.time.Instant;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ServiceRequestService {

    private static final Logger log = LoggerFactory.getLogger(ServiceRequestService.class);

    private final ServiceRequestRepository repository;
    private final OutboxEventService outboxEventService;

    public ServiceRequestService(ServiceRequestRepository repository, OutboxEventService outboxEventService) {
        this.repository = repository;
        this.outboxEventService = outboxEventService;
    }

    // Both saves below (the business row and the outbox row) must commit
    // together or not at all - that atomicity is the entire point of the
    // outbox pattern, and it only holds because this whole method runs in
    // one transaction. See OutboxEventService/OutboxPublisher for the rest.
    @Transactional
    public ServiceRequestResponse createServiceRequest(ServiceRequestCreateRequest request) {
        UUID correlationId = UUID.randomUUID();
        MDC.put("correlationId", correlationId.toString());
        try {
            log.atInfo().addKeyValue("event", "SERVICE_REQUEST_RECEIVED").log("Service request received");

            ServiceRequest serviceRequest = new ServiceRequest(
                    correlationId,
                    request.source(),
                    request.customerId(),
                    request.category(),
                    request.subcategory(),
                    request.shortDescription(),
                    request.description(),
                    request.priority(),
                    RequestStatus.RECEIVED);

            repository.save(serviceRequest);
            log.atInfo().addKeyValue("event", "DATABASE_PERSISTED").log("Service request persisted to database");

            ServiceRequestCreatedEvent event = new ServiceRequestCreatedEvent(
                    UUID.randomUUID(),
                    ServiceRequestCreatedEvent.EVENT_TYPE,
                    ServiceRequestCreatedEvent.EVENT_VERSION,
                    Instant.now(),
                    correlationId,
                    request.source(),
                    new ServiceRequestCreatedEvent.Payload(
                            request.customerId(),
                            request.category(),
                            request.subcategory(),
                            request.shortDescription(),
                            request.description(),
                            request.priority()));

            MDC.put("eventId", event.eventId().toString());
            outboxEventService.enqueue(event);

            return new ServiceRequestResponse(correlationId, RequestStatus.RECEIVED);
        } finally {
            MDC.clear();
        }
    }
}
