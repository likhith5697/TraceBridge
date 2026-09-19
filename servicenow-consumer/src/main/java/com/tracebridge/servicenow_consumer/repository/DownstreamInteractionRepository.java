package com.tracebridge.servicenow_consumer.repository;

import com.tracebridge.servicenow_consumer.entity.DownstreamInteraction;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DownstreamInteractionRepository extends JpaRepository<DownstreamInteraction, Long> {

    boolean existsByEventId(UUID eventId);
}
