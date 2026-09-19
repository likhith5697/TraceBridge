package com.tracebridge.servicenow_consumer.servicenow;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.ObjectMapper;

class ServiceNowClientTest {

    private MockWebServer server;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() throws IOException {
        server = new MockWebServer();
        server.start();
        objectMapper = new ObjectMapper();
    }

    @AfterEach
    void tearDown() throws IOException {
        server.shutdown();
    }

    private ServiceNowClient clientWithTimeouts(long connectTimeoutMs, long readTimeoutMs) {
        ServiceNowProperties properties =
                new ServiceNowProperties(server.url("/").toString(), "user", "pass", connectTimeoutMs, readTimeoutMs);
        HttpClient httpClient =
                HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connectTimeoutMs)).build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(Duration.ofMillis(readTimeoutMs));

        return new ServiceNowClient(
                RestClient.builder(), requestFactory, headers -> {}, properties, objectMapper);
    }

    private ServiceNowIncidentRequest sampleRequest() {
        return new ServiceNowIncidentRequest("short desc", "full description", "1", "1", "network");
    }

    @Test
    void returnsSuccessOn201() {
        server.enqueue(new MockResponse()
                .setResponseCode(201)
                .setBody("{\"result\":{\"sys_id\":\"abc123\",\"number\":\"INC0012345\"}}")
                .setHeader("Content-Type", "application/json"));

        ServiceNowClient client = clientWithTimeouts(5000, 5000);
        ServiceNowResult result = client.createIncident(sampleRequest(), UUID.randomUUID().toString());

        assertThat(result.success()).isTrue();
        assertThat(result.httpStatus()).isEqualTo(201);
        assertThat(result.sysId()).isEqualTo("abc123");
        assertThat(result.number()).isEqualTo("INC0012345");
    }

    @Test
    void returnsFailureOn400() {
        server.enqueue(new MockResponse().setResponseCode(400).setBody("{\"error\":\"bad request\"}"));

        ServiceNowClient client = clientWithTimeouts(5000, 5000);
        ServiceNowResult result = client.createIncident(sampleRequest(), UUID.randomUUID().toString());

        assertThat(result.success()).isFalse();
        assertThat(result.httpStatus()).isEqualTo(400);
        assertThat(result.errorCode()).isEqualTo("BAD_REQUEST");
    }

    @Test
    void returnsFailureOn401() {
        server.enqueue(new MockResponse().setResponseCode(401).setBody("{\"error\":\"unauthorized\"}"));

        ServiceNowClient client = clientWithTimeouts(5000, 5000);
        ServiceNowResult result = client.createIncident(sampleRequest(), UUID.randomUUID().toString());

        assertThat(result.success()).isFalse();
        assertThat(result.httpStatus()).isEqualTo(401);
        assertThat(result.errorCode()).isEqualTo("UNAUTHORIZED");
    }

    @Test
    void returnsFailureOn500() {
        server.enqueue(new MockResponse().setResponseCode(500).setBody("{\"error\":\"server error\"}"));

        ServiceNowClient client = clientWithTimeouts(5000, 5000);
        ServiceNowResult result = client.createIncident(sampleRequest(), UUID.randomUUID().toString());

        assertThat(result.success()).isFalse();
        assertThat(result.httpStatus()).isEqualTo(500);
        assertThat(result.errorCode()).isEqualTo("SERVER_ERROR");
    }

    @Test
    void returnsFailureOnReadTimeout() {
        server.enqueue(new MockResponse().setHeadersDelay(2, TimeUnit.SECONDS).setResponseCode(200));

        ServiceNowClient client = clientWithTimeouts(5000, 200);
        ServiceNowResult result = client.createIncident(sampleRequest(), UUID.randomUUID().toString());

        assertThat(result.success()).isFalse();
        assertThat(result.httpStatus()).isNull();
        assertThat(result.errorCode()).isEqualTo("TIMEOUT");
    }

    @Test
    void returnsFailureOnConnectionRefused() throws IOException {
        int closedPort;
        try (ServerSocket socket = new ServerSocket(0)) {
            closedPort = socket.getLocalPort();
        }
        // socket is now closed - nothing is listening on closedPort

        ServiceNowProperties properties =
                new ServiceNowProperties("http://localhost:" + closedPort, "user", "pass", 2000, 2000);
        JdkClientHttpRequestFactory requestFactory =
                new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build());
        requestFactory.setReadTimeout(Duration.ofSeconds(2));

        ServiceNowClient client =
                new ServiceNowClient(RestClient.builder(), requestFactory, headers -> {}, properties, objectMapper);
        ServiceNowResult result = client.createIncident(sampleRequest(), UUID.randomUUID().toString());

        assertThat(result.success()).isFalse();
        assertThat(result.httpStatus()).isNull();
        assertThat(result.errorCode()).isEqualTo("CONNECTION_ERROR");
    }

    @Test
    void returnsNotConfiguredWhenBaseUrlBlank() {
        ServiceNowProperties properties = new ServiceNowProperties("", "user", "pass", 1000, 1000);
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory();

        ServiceNowClient client =
                new ServiceNowClient(RestClient.builder(), requestFactory, headers -> {}, properties, objectMapper);
        ServiceNowResult result = client.createIncident(sampleRequest(), UUID.randomUUID().toString());

        assertThat(result.success()).isFalse();
        assertThat(result.errorCode()).isEqualTo("NOT_CONFIGURED");
    }
}
