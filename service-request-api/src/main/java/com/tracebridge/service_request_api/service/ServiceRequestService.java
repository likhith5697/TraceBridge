package com.tracebridge.service_request_api.service;

import com.tracebridge.service_request_api.dto.ServiceRequestCreateRequest;
import com.tracebridge.service_request_api.dto.ServiceRequestResponse;
import com.tracebridge.service_request_api.entity.RequestStatus;
import com.tracebridge.service_request_api.entity.ServiceRequest;
import com.tracebridge.service_request_api.event.ServiceRequestCreatedEvent;
import com.tracebridge.service_request_api.event.ServiceRequestEventPublisher;
import com.tracebridge.service_request_api.repository.ServiceRequestRepository;
import java.time.Instant;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Service;

@Service
public class ServiceRequestService {

    private static final Logger log = LoggerFactory.getLogger(ServiceRequestService.class);

    private final ServiceRequestRepository repository;
    private final ServiceRequestEventPublisher eventPublisher;

    public ServiceRequestService(ServiceRequestRepository repository, ServiceRequestEventPublisher eventPublisher) {
        this.repository = repository;
        this.eventPublisher = eventPublisher;
    }

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

            // Spring Data JPA wraps this single save() in its own transaction and commits
            // before this method continues - the Kafka publish below happens strictly after
            // the row is durably persisted.
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
            eventPublisher.publish(event);

            return new ServiceRequestResponse(correlationId, RequestStatus.RECEIVED);
        } finally {
            MDC.clear();
        }
    }
}
