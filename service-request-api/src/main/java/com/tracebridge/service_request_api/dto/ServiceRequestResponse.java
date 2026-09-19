package com.tracebridge.service_request_api.dto;

import com.tracebridge.service_request_api.entity.RequestStatus;
import java.util.UUID;

public record ServiceRequestResponse(UUID correlationId, RequestStatus status) {}
