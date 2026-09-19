package com.tracebridge.servicenow_consumer.servicenow;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import tools.jackson.databind.ObjectMapper;

@Component
public class ServiceNowClient {

    private static final String CREATE_INCIDENT_PATH = "/api/now/table/incident";
    private static final String CORRELATION_ID_HEADER = "X-Correlation-Id";

    private final RestClient restClient;
    private final ServiceNowAuthentication authentication;
    private final ServiceNowProperties properties;
    private final ObjectMapper objectMapper;

    public ServiceNowClient(
            RestClient.Builder restClientBuilder,
            ClientHttpRequestFactory requestFactory,
            ServiceNowAuthentication authentication,
            ServiceNowProperties properties,
            ObjectMapper objectMapper) {
        this.authentication = authentication;
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.restClient = restClientBuilder
                .baseUrl(properties.isConfigured() ? properties.baseUrl() : "http://unconfigured.invalid")
                .requestFactory(requestFactory)
                .build();
    }

    public String endpoint() {
        return CREATE_INCIDENT_PATH;
    }

    public ServiceNowResult createIncident(ServiceNowIncidentRequest request, String correlationId) {
        if (!properties.isConfigured()) {
            return ServiceNowResult.notConfigured(0);
        }

        long start = System.currentTimeMillis();
        try {
            ResponseEntity<String> response = restClient
                    .post()
                    .uri(CREATE_INCIDENT_PATH)
                    .header(CORRELATION_ID_HEADER, correlationId)
                    .headers(this::authenticate)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .toEntity(String.class);

            long duration = System.currentTimeMillis() - start;
            String body = response.getBody();
            ServiceNowIncidentResponse parsed = objectMapper.readValue(body, ServiceNowIncidentResponse.class);
            return ServiceNowResult.success(
                    response.getStatusCode().value(),
                    parsed.result() != null ? parsed.result().sysId() : null,
                    parsed.result() != null ? parsed.result().number() : null,
                    body,
                    duration);
        } catch (RestClientResponseException e) {
            long duration = System.currentTimeMillis() - start;
            return ServiceNowResult.failure(
                    e.getStatusCode().value(),
                    errorCodeFor(e.getStatusCode()),
                    e.getMessage(),
                    e.getResponseBodyAsString(),
                    duration);
        } catch (ResourceAccessException e) {
            long duration = System.currentTimeMillis() - start;
            String errorCode = isTimeout(e) ? "TIMEOUT" : "CONNECTION_ERROR";
            return ServiceNowResult.failure(null, errorCode, e.getMessage(), null, duration);
        }
    }

    private void authenticate(HttpHeaders headers) {
        authentication.apply(headers);
    }

    private boolean isTimeout(ResourceAccessException e) {
        Throwable cause = e.getCause();
        return cause instanceof java.net.SocketTimeoutException
                || cause instanceof java.net.http.HttpTimeoutException;
    }

    private String errorCodeFor(HttpStatusCode status) {
        return switch (status.value()) {
            case 400 -> "BAD_REQUEST";
            case 401 -> "UNAUTHORIZED";
            case 403 -> "FORBIDDEN";
            case 404 -> "NOT_FOUND";
            case 429 -> "RATE_LIMITED";
            default -> status.is5xxServerError() ? "SERVER_ERROR" : "HTTP_ERROR";
        };
    }
}
