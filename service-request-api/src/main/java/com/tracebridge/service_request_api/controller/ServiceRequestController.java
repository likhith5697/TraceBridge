package com.tracebridge.service_request_api.controller;

import com.tracebridge.service_request_api.dto.ServiceRequestCreateRequest;
import com.tracebridge.service_request_api.dto.ServiceRequestResponse;
import com.tracebridge.service_request_api.service.ServiceRequestService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/service-requests")
public class ServiceRequestController {

    private final ServiceRequestService service;

    public ServiceRequestController(ServiceRequestService service) {
        this.service = service;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.ACCEPTED)
    public ServiceRequestResponse createServiceRequest(@Valid @RequestBody ServiceRequestCreateRequest request) {
        return service.createServiceRequest(request);
    }
}
