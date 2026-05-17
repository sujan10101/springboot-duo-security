package com.example.duosecurity.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class AuthResponse {
    private String accessToken;
    private String tokenType;
    private Long expiresIn;
    // "authenticated" | "waiting" | "denied"
    private String status;
    private String message;
}
