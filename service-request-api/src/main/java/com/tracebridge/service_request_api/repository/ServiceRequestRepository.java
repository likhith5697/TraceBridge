package com.tracebridge.service_request_api.repository;

import com.tracebridge.service_request_api.entity.ServiceRequest;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ServiceRequestRepository extends JpaRepository<ServiceRequest, Long> {}
