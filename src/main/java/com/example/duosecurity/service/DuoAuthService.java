package com.example.duosecurity.service;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.stream.StreamSupport;

@Service
@RequiredArgsConstructor
@Slf4j
public class DuoAuthService {

    /** Sentinel returned when Duo is configured to bypass a user. */
    static final String DUO_BYPASS = "DUO_BYPASS";

    /** Sentinel returned when the user has no push device — must use passcode instead. */
    static final String DUO_PASSCODE_ONLY = "DUO_PASSCODE_ONLY";

    /** Mock passcode accepted when mock mode is enabled. */
    private static final String MOCK_PASSCODE = "000000";

    private final DuoApiClient duoApiClient;

    @Value("${duo.mock-enabled:false}")
    private boolean mockEnabled;

    @Value("${duo.mock-txid:mock-txid-00000}")
    private String mockTxid;

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Runs preauth then kicks off an async push.
     * @return Duo txid to be polled later, or {@link #DUO_BYPASS} if Duo allows the user without a factor.
     */
    public String initiateAuth(String username) {
        if (mockEnabled) {
            log.warn("Duo mock mode active — skipping real MFA for '{}'", username);
            return mockTxid;
        }
        try {
            JsonNode preauth = duoApiClient.preauth(username);
            String result    = preauth.path("response").path("result").asText();

            return switch (result) {
                case "deny"   -> {
                    log.warn("Duo denied access for user '{}'", username);
                    throw new RuntimeException("Duo access denied for user: " + username);
                }
                case "allow"  -> {
                    log.info("Duo bypass policy active for '{}' — skipping MFA factor", username);
                    yield DUO_BYPASS;
                }
                case "enroll" -> {
                    log.warn("User '{}' is not enrolled in Duo", username);
                    throw new RuntimeException("User '" + username + "' is not enrolled in Duo — enroll them in the Duo Admin Panel first");
                }
                default -> {
                    JsonNode devices = preauth.path("response").path("devices");
                    boolean canPush = StreamSupport.stream(devices.spliterator(), false)
                            .anyMatch(d -> d.path("capabilities").toString().contains("push"));
                    if (!canPush) {
                        log.info("No push-capable device for '{}' — passcode required", username);
                        yield DUO_PASSCODE_ONLY;
                    }
                    yield duoApiClient.authAsync(username);
                }
            };
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            log.error("Duo preauth/auth failed for '{}': {}", username, e.getMessage());
            throw new RuntimeException("MFA initiation failed", e);
        }
    }

    /**
     * Polls the Duo push result for a previously started transaction.
     * @return "waiting" | "allow" | "deny"
     */
    public String pollStatus(String txid) {
        if (DUO_PASSCODE_ONLY.equals(txid)) {
            throw new RuntimeException("No push device enrolled — use POST /auth/mfa/passcode instead");
        }
        if (mockEnabled || DUO_BYPASS.equals(txid)) {
            return "allow";
        }
        try {
            return duoApiClient.authStatus(txid);
        } catch (Exception e) {
            log.error("Duo auth_status poll failed for txid '{}': {}", txid, e.getMessage());
            throw new RuntimeException("MFA status check failed", e);
        }
    }

    /**
     * Synchronously verifies a TOTP/SMS/hardware passcode.
     * @return true if Duo approved
     */
    public boolean verifyPasscode(String username, String passcode) {
        if (mockEnabled) {
            return MOCK_PASSCODE.equals(passcode);
        }
        try {
            return duoApiClient.authPasscode(username, passcode);
        } catch (Exception e) {
            log.error("Duo passcode verify failed for '{}': {}", username, e.getMessage());
            throw new RuntimeException("MFA passcode verification failed", e);
        }
    }
}
