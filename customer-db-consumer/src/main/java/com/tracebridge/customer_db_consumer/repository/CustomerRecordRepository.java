package com.tracebridge.customer_db_consumer.repository;

import com.tracebridge.customer_db_consumer.entity.CustomerRecord;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CustomerRecordRepository extends JpaRepository<CustomerRecord, Long> {

    boolean existsByEventId(UUID eventId);
}
