package com.tracebridge.service_request_api.repository;

import com.tracebridge.service_request_api.entity.OutboxEvent;
import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OutboxEventRepository extends JpaRepository<OutboxEvent, Long> {

    List<OutboxEvent> findBySentFalseOrderByCreatedAtAsc(Pageable pageable);
}
