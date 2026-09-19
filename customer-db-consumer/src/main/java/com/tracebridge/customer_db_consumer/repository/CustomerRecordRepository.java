package com.tracebridge.customer_db_consumer.repository;

import com.tracebridge.customer_db_consumer.entity.CustomerRecord;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CustomerRecordRepository extends JpaRepository<CustomerRecord, Long> {}
