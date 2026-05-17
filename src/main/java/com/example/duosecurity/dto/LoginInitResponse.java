package com.example.duosecurity.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class LoginInitResponse {
    // Short-lived JWT (5 min) containing username + Duo txid; NOT usable as an auth token
    private String pendingToken;
    private String message;
    // "push" or "passcode"
    private String factor;
}
