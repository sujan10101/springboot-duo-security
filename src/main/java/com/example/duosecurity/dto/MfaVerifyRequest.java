package com.example.duosecurity.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class MfaVerifyRequest {

    @NotBlank(message = "pendingToken is required")
    private String pendingToken;
}
