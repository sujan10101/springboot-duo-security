package com.example.duosecurity.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class MfaPasscodeRequest {

    @NotBlank(message = "pendingToken is required")
    private String pendingToken;

    @NotBlank(message = "passcode is required")
    private String passcode;
}
