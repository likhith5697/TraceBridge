package com.tracebridge.servicenow_consumer.repository;

import com.tracebridge.servicenow_consumer.entity.DownstreamInteraction;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DownstreamInteractionRepository extends JpaRepository<DownstreamInteraction, Long> {}
