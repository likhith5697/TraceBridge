package com.tracebridge.servicenow_consumer.servicenow;

import com.tracebridge.servicenow_consumer.event.Priority;
import com.tracebridge.servicenow_consumer.event.ServiceRequestCreatedEvent;
import java.util.Locale;
import org.springframework.stereotype.Component;

// ServiceNow derives "priority" itself from (urgency, impact) via its own business rule,
// so we set those two instead - see ServiceNowIncidentMapperTest for the exact mapping table.
@Component
public class ServiceNowIncidentMapper {

    public ServiceNowIncidentRequest toIncidentRequest(ServiceRequestCreatedEvent event) {
        ServiceRequestCreatedEvent.Payload payload = event.payload();
        UrgencyImpact urgencyImpact = mapPriority(payload.priority());

        String description = payload.description()
                + "\n\nTraceBridge correlationId: " + event.correlationId()
                + "\nCustomer: " + payload.customerId();

        return new ServiceNowIncidentRequest(
                payload.shortDescription(),
                description,
                urgencyImpact.urgency(),
                urgencyImpact.impact(),
                payload.category().toLowerCase(Locale.ROOT));
    }

    private UrgencyImpact mapPriority(Priority priority) {
        return switch (priority) {
            case P1 -> new UrgencyImpact("1", "1");
            case P2 -> new UrgencyImpact("1", "2");
            case P3 -> new UrgencyImpact("2", "2");
            case P4 -> new UrgencyImpact("3", "3");
        };
    }

    private record UrgencyImpact(String urgency, String impact) {}
}
