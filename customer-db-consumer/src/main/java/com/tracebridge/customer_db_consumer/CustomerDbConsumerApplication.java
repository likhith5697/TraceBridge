package com.tracebridge.customer_db_consumer;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class CustomerDbConsumerApplication {

    public static void main(String[] args) {
        SpringApplication.run(CustomerDbConsumerApplication.class, args);
    }
}
