package com.tracebridge.service_request_api.dto;

import com.tracebridge.service_request_api.entity.Priority;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record ServiceRequestCreateRequest(
        @NotBlank @Size(max = 50) String source,
        @NotBlank @Size(max = 50) String customerId,
        @NotBlank @Size(max = 50) String category,
        @NotBlank @Size(max = 50) String subcategory,
        @NotBlank @Size(max = 255) String shortDescription,
        @NotBlank @Size(max = 2000) String description,
        @NotNull Priority priority) {}
