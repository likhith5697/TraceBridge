package com.tracebridge.servicenow_consumer.servicenow;

import static org.assertj.core.api.Assertions.assertThat;

import com.tracebridge.servicenow_consumer.event.Priority;
import com.tracebridge.servicenow_consumer.event.ServiceRequestCreatedEvent;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class ServiceNowIncidentMapperTest {

    private final ServiceNowIncidentMapper mapper = new ServiceNowIncidentMapper();

    private ServiceRequestCreatedEvent eventWith(Priority priority) {
        ServiceRequestCreatedEvent.Payload payload = new ServiceRequestCreatedEvent.Payload(
                "CUS-92831", "NETWORK", "CONNECTIVITY", "Customer circuit unavailable",
                "Customer reports complete loss of connectivity", priority);

        return new ServiceRequestCreatedEvent(
                UUID.randomUUID(),
                ServiceRequestCreatedEvent.SUPPORTED_EVENT_TYPE,
                ServiceRequestCreatedEvent.SUPPORTED_EVENT_VERSION,
                Instant.now(),
                UUID.randomUUID(),
                "CUSTOMER_PORTAL",
                payload);
    }

    @ParameterizedTest
    @CsvSource({"P1,1,1", "P2,1,2", "P3,2,2", "P4,3,3"})
    void mapsPriorityToUrgencyAndImpact(Priority priority, String urgency, String impact) {
        ServiceNowIncidentRequest request = mapper.toIncidentRequest(eventWith(priority));

        assertThat(request.urgency()).isEqualTo(urgency);
        assertThat(request.impact()).isEqualTo(impact);
    }

    @Test
    void mapsBusinessFieldsAndLowercasesCategory() {
        ServiceRequestCreatedEvent event = eventWith(Priority.P2);

        ServiceNowIncidentRequest request = mapper.toIncidentRequest(event);

        assertThat(request.shortDescription()).isEqualTo("Customer circuit unavailable");
        assertThat(request.category()).isEqualTo("network");
        assertThat(request.description()).contains("Customer reports complete loss of connectivity");
        assertThat(request.description()).contains(event.correlationId().toString());
        assertThat(request.description()).contains("CUS-92831");
    }
}
