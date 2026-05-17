package com.example.duosecurity.service;

import com.example.duosecurity.dto.*;
import com.example.duosecurity.entity.User;
import com.example.duosecurity.repository.UserRepository;
import com.example.duosecurity.security.JwtService;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class AuthService {

    private final UserRepository  userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService      jwtService;
    private final DuoAuthService  duoAuthService;
    private final DuoApiClient    duoApiClient;

    @Value("${app.jwt.expiration}")
    private long jwtExpiration;

    // ── Step 1: password validation + Duo push ────────────────────────────────

    /**
     * Validates username/password, initiates a Duo push, and returns a
     * short-lived pending token embedding the Duo txid.
     */
    public LoginInitResponse initiateLogin(LoginRequest request) {
        User user = userRepository.findByUsername(request.getUsername())
                .orElseThrow(() -> new BadCredentialsException("Invalid credentials"));

        if (!user.isEnabled()) {
            throw new BadCredentialsException("Account is disabled");
        }
        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BadCredentialsException("Invalid credentials");
        }

        String txid         = duoAuthService.initiateAuth(user.getUsername());
        String pendingToken = jwtService.generatePendingToken(user.getUsername(), txid);

        boolean bypass       = DuoAuthService.DUO_BYPASS.equals(txid);
        boolean passcodeOnly = DuoAuthService.DUO_PASSCODE_ONLY.equals(txid);
        String message = bypass       ? "Duo bypass active — call /auth/mfa/verify to complete"
                       : passcodeOnly ? "No push device — call /auth/mfa/passcode with your TOTP code"
                       :                "Duo push sent to your registered device — call /auth/mfa/verify to poll";

        log.info("Login step-1 complete for '{}' (bypass={})", user.getUsername(), bypass);
        return new LoginInitResponse(pendingToken, message, "push");
    }

    // ── Step 2a: poll Duo push result ─────────────────────────────────────────

    /**
     * Decodes the pending token, polls Duo for push approval, and issues a
     * full JWT on "allow". Returns 202 body when still "waiting".
     */
    public AuthResponse verifyMfaPush(MfaVerifyRequest request) {
        String pending = request.getPendingToken();
        if (!jwtService.isValidPendingToken(pending)) {
            throw new BadCredentialsException("Invalid or expired MFA session token");
        }

        String username = jwtService.extractUsername(pending);
        String txid     = jwtService.extractDuoTxid(pending);
        String result   = duoAuthService.pollStatus(txid);

        return switch (result) {
            case "allow"   -> buildFullJwt(username);
            case "waiting" -> AuthResponse.builder()
                                 .status("waiting")
                                 .message("Waiting for Duo approval — try again shortly")
                                 .build();
            case "deny"    -> throw new BadCredentialsException("Duo authentication denied");
            default        -> throw new BadCredentialsException("Unexpected Duo status: " + result);
        };
    }

    // ── Step 2b: verify TOTP / hardware passcode ──────────────────────────────

    /**
     * Decodes the pending token, verifies a TOTP/passcode with Duo, and issues
     * a full JWT on approval.
     */
    public AuthResponse verifyMfaPasscode(MfaPasscodeRequest request) {
        String pending = request.getPendingToken();
        if (!jwtService.isValidPendingToken(pending)) {
            throw new BadCredentialsException("Invalid or expired MFA session token");
        }

        String username = jwtService.extractUsername(pending);
        boolean approved = duoAuthService.verifyPasscode(username, request.getPasscode());

        if (!approved) {
            throw new BadCredentialsException("Duo passcode verification failed");
        }
        return buildFullJwt(username);
    }

    // ── Preauth ───────────────────────────────────────────────────────────────

    public PreauthResponse preauth(String username) {
        try {
            JsonNode raw      = duoApiClient.preauth(username);
            JsonNode resp     = raw.path("response");
            String result     = resp.path("result").asText();
            String statusMsg  = resp.path("status_msg").asText();

            List<PreauthResponse.DeviceInfo> devices = new ArrayList<>();
            for (JsonNode d : resp.path("devices")) {
                List<String> caps = new ArrayList<>();
                for (JsonNode c : d.path("capabilities")) caps.add(c.asText());
                devices.add(PreauthResponse.DeviceInfo.builder()
                        .device(d.path("device").asText())
                        .displayName(d.path("display_name").asText())
                        .type(d.path("type").asText())
                        .capabilities(caps)
                        .build());
            }

            log.info("Preauth check for '{}': result={}", username, result);
            return PreauthResponse.builder()
                    .result(result)
                    .statusMsg(statusMsg)
                    .devices(devices)
                    .build();
        } catch (Exception e) {
            log.error("Preauth check failed for '{}': {}", username, e.getMessage());
            throw new RuntimeException("Preauth check failed", e);
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private AuthResponse buildFullJwt(String username) {
        User user = userRepository.findByUsername(username)
                .orElseThrow(() -> new UsernameNotFoundException("User not found"));

        List<String> roles = user.getRoles().stream().toList();
        String jwt = jwtService.generateAuthToken(username, roles);

        log.info("Full JWT issued for '{}'", username);
        return AuthResponse.builder()
                .accessToken(jwt)
                .tokenType("Bearer")
                .expiresIn(jwtExpiration / 1000)
                .status("authenticated")
                .build();
    }
}
