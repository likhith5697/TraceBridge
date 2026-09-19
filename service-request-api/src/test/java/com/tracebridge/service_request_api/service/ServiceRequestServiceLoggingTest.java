package com.tracebridge.service_request_api.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.tracebridge.service_request_api.dto.ServiceRequestCreateRequest;
import com.tracebridge.service_request_api.dto.ServiceRequestResponse;
import com.tracebridge.service_request_api.entity.Priority;
import com.tracebridge.service_request_api.event.ServiceRequestEventPublisher;
import com.tracebridge.service_request_api.repository.ServiceRequestRepository;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

// Verifies correlationId reaches every log line for a request via MDC, and MDC is cleared
// afterward so it can't leak into whatever the next request on this (reused) thread logs.
class ServiceRequestServiceLoggingTest {

    private final ServiceRequestRepository repository = mock(ServiceRequestRepository.class);
    private final ServiceRequestEventPublisher eventPublisher = mock(ServiceRequestEventPublisher.class);
    private final ServiceRequestService service = new ServiceRequestService(repository, eventPublisher);

    private Logger rootLogger;
    private ListAppender<ILoggingEvent> appender;

    @BeforeEach
    void setUp() {
        rootLogger = (Logger) LoggerFactory.getLogger(Logger.ROOT_LOGGER_NAME);
        appender = new ListAppender<>();
        appender.start();
        rootLogger.addAppender(appender);
    }

    @AfterEach
    void tearDown() {
        rootLogger.detachAppender(appender);
        MDC.clear();
    }

    private ServiceRequestCreateRequest sampleRequest() {
        return new ServiceRequestCreateRequest(
                "CUSTOMER_PORTAL", "CUS-1", "NETWORK", "CONNECTIVITY", "short", "full description", Priority.P2);
    }

    @Test
    void attachesCorrelationIdToEveryLogLineAndClearsMdcAfterward() {
        ServiceRequestResponse response = service.createServiceRequest(sampleRequest());

        List<ILoggingEvent> events = appender.list;
        assertThat(events).isNotEmpty();
        for (ILoggingEvent event : events) {
            assertThat(event.getMDCPropertyMap())
                    .containsEntry("correlationId", response.correlationId().toString());
        }
        assertThat(MDC.get("correlationId")).isNull();
        assertThat(MDC.get("eventId")).isNull();
    }

    @Test
    void doesNotLeakCorrelationIdIntoTheNextRequestOnTheSameThread() {
        ServiceRequestResponse first = service.createServiceRequest(sampleRequest());
        appender.list.clear();

        ServiceRequestResponse second = service.createServiceRequest(sampleRequest());

        for (ILoggingEvent event : appender.list) {
            assertThat(event.getMDCPropertyMap()).doesNotContainValue(first.correlationId().toString());
            assertThat(event.getMDCPropertyMap()).containsEntry("correlationId", second.correlationId().toString());
        }
    }
}
