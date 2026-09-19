package com.tracebridge.servicenow_consumer;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class ServicenowConsumerApplication {

    public static void main(String[] args) {
        SpringApplication.run(ServicenowConsumerApplication.class, args);
    }
}
