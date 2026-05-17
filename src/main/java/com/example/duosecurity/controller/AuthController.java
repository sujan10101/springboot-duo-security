package com.example.duosecurity.controller;

import com.example.duosecurity.dto.*;
import com.example.duosecurity.service.AuthService;
import org.springframework.web.bind.annotation.RequestParam;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    /**
     * Step 1 — validate password and trigger a Duo push.
     * Returns a short-lived pendingToken; not usable as an auth token.
     *
     * POST /auth/login
     * Body: { "username": "alice", "password": "password123" }
     */
    @PostMapping("/login")
    public ResponseEntity<LoginInitResponse> login(@Valid @RequestBody LoginRequest request) {
        return ResponseEntity.ok(authService.initiateLogin(request));
    }

    /**
     * Check a user's Duo enrollment status and available MFA factors.
     * Useful for debugging device capabilities before attempting login.
     *
     * GET /auth/preauth?username=admin
     */
    @GetMapping("/preauth")
    public ResponseEntity<PreauthResponse> preauth(@RequestParam String username) {
        return ResponseEntity.ok(authService.preauth(username));
    }

    /**
     * Step 2a — poll Duo for push approval.
     * Returns 200 + JWT when approved, or 202 when still waiting.
     * Call repeatedly until non-202.
     *
     * POST /auth/mfa/verify
     * Body: { "pendingToken": "<token from /auth/login>" }
     */
    @PostMapping("/mfa/verify")
    public ResponseEntity<AuthResponse> verifyPush(@Valid @RequestBody MfaVerifyRequest request) {
        AuthResponse resp = authService.verifyMfaPush(request);
        if ("waiting".equals(resp.getStatus())) {
            return ResponseEntity.accepted().body(resp);
        }
        return ResponseEntity.ok(resp);
    }

    /**
     * Step 2b — verify a TOTP / SMS / hardware passcode instead of push.
     *
     * POST /auth/mfa/passcode
     * Body: { "pendingToken": "...", "passcode": "123456" }
     * (In mock mode any passcode "000000" is accepted.)
     */
    @PostMapping("/mfa/passcode")
    public ResponseEntity<AuthResponse> verifyPasscode(@Valid @RequestBody MfaPasscodeRequest request) {
        return ResponseEntity.ok(authService.verifyMfaPasscode(request));
    }
}
