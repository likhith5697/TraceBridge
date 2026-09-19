package com.tracebridge.servicenow_consumer.servicenow;

import java.util.List;
import java.util.Locale;
import java.util.Set;
import org.springframework.stereotype.Component;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

// Redacts anything that looks like a credential before a payload is persisted or logged.
// This is a defensive second layer - the primary safeguard is that ServiceNowClient never
// hands HTTP headers (where the real Authorization value lives) to anything that persists
// or logs; only request/response bodies ever reach this class.
@Component
public class PayloadSanitizer {

    private static final Set<String> SENSITIVE_FIELD_NAMES =
            Set.of("authorization", "password", "access_token", "accesstoken", "token", "cookie", "secret");

    private final ObjectMapper objectMapper;

    public PayloadSanitizer(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public String sanitize(String json) {
        if (json == null) {
            return null;
        }
        try {
            JsonNode node = objectMapper.readTree(json);
            redact(node);
            return objectMapper.writeValueAsString(node);
        } catch (JacksonException e) {
            return "[unparseable payload, length=" + json.length() + "]";
        }
    }

    private void redact(JsonNode node) {
        if (node instanceof ObjectNode obj) {
            List<String> fieldNames = List.copyOf(obj.propertyNames());
            for (String name : fieldNames) {
                if (SENSITIVE_FIELD_NAMES.contains(name.toLowerCase(Locale.ROOT))) {
                    obj.put(name, "[REDACTED]");
                } else {
                    redact(obj.get(name));
                }
            }
        } else if (node instanceof ArrayNode array) {
            array.forEach(this::redact);
        }
    }
}
