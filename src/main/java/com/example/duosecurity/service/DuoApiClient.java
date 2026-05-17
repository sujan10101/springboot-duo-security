package com.example.duosecurity.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Base64;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import java.util.stream.Collectors;

/**
 * Low-level Duo Auth API v2 client.
 * Implements Duo's HMAC-SHA1 request signing:
 *   canon  = date\nMETHOD\nhost\npath\nurl-encoded-sorted-params
 *   header = Basic base64(ikey:hex(hmac_sha1(skey, canon)))
 */
@Component
@Slf4j
public class DuoApiClient {

    private static final DateTimeFormatter RFC_2822 =
            DateTimeFormatter.ofPattern("EEE, dd MMM yyyy HH:mm:ss Z", Locale.ENGLISH);

    @Value("${duo.integration-key}")
    private String integrationKey;

    @Value("${duo.secret-key}")
    private String secretKey;

    @Value("${duo.api-hostname}")
    private String apiHostname;

    private final HttpClient http     = HttpClient.newHttpClient();
    private final ObjectMapper mapper = new ObjectMapper();

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Checks whether the user is enrolled and which factor types are available.
     * Returns the full Duo JSON response.
     */
    public JsonNode preauth(String username) throws Exception {
        log.debug("Duo preauth request for user '{}'", username);
        Map<String, String> params = new TreeMap<>();
        params.put("username", username);
        JsonNode response = post("/auth/v2/preauth", params);
        JsonNode resp = response.path("response");
        log.info("Duo preauth result for '{}': result={}, status_msg={}, devices={}",
                username,
                resp.path("result").asText(),
                resp.path("status_msg").asText(),
                resp.path("devices"));
        return response;
    }

    /**
     * Starts an async push authentication and returns the Duo transaction ID.
     * The caller must later poll {@link #authStatus(String)}.
     */
    public String authAsync(String username) throws Exception {
        log.debug("Duo async push request for user '{}'", username);
        Map<String, String> params = new TreeMap<>();
        params.put("username", username);
        params.put("factor", "push");
        params.put("device", "auto");
        params.put("async", "1");

        JsonNode body = post("/auth/v2/auth", params);
        assertOk(body, "Duo async auth");
        String txid = body.path("response").path("txid").asText();
        log.info("Duo push sent for '{}', txid={}", username, txid);
        return txid;
    }

    /**
     * Polls the result of an async push.
     * @return "waiting" | "allow" | "deny"
     */
    public String authStatus(String txid) throws Exception {
        log.debug("Duo auth_status poll for txid={}", txid);
        Map<String, String> params = new TreeMap<>();
        params.put("txid", txid);

        JsonNode body = get("/auth/v2/auth_status", params);
        assertOk(body, "Duo auth_status");
        String result = body.path("response").path("result").asText();
        log.info("Duo auth_status for txid={}: result={}", txid, result);
        return result;
    }

    /**
     * Synchronously verifies a TOTP/SMS/hardware passcode.
     * @return true if Duo approved
     */
    public boolean authPasscode(String username, String passcode) throws Exception {
        log.debug("Duo passcode verification request for user '{}'", username);
        Map<String, String> params = new TreeMap<>();
        params.put("username", username);
        params.put("factor", "passcode");
        params.put("passcode", passcode);

        JsonNode body = post("/auth/v2/auth", params);
        assertOk(body, "Duo passcode auth");
        JsonNode resp = body.path("response");
        boolean approved = "allow".equals(resp.path("result").asText());
        log.info("Duo passcode result for '{}': result={}, status={}, status_msg={}",
                username,
                resp.path("result").asText(),
                resp.path("status").asText(),
                resp.path("status_msg").asText());
        return approved;
    }
    // ── HTTP helpers ──────────────────────────────────────────────────────────

    private JsonNode post(String path, Map<String, String> params) throws Exception {
        String date        = now();
        String paramString = encodeParams(params);
        String authHeader  = sign("POST", path, paramString, date);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("https://" + apiHostname + path))
                .header("Authorization", authHeader)
                .header("Date", date)
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(paramString))
                .build();

        HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
        return mapper.readTree(response.body());
    }

    private JsonNode get(String path, Map<String, String> params) throws Exception {
        String date        = now();
        String paramString = encodeParams(params);
        String authHeader  = sign("GET", path, paramString, date);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("https://" + apiHostname + path + "?" + paramString))
                .header("Authorization", authHeader)
                .header("Date", date)
                .GET()
                .build();

        HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
        return mapper.readTree(response.body());
    }

    // ── Signing ───────────────────────────────────────────────────────────────

    /**
     * Builds the Authorization header value using Duo's HMAC-SHA1 signing scheme.
     */
    private String sign(String method, String path, String params, String date) throws Exception {
        String canon = String.join("\n",
                date,
                method.toUpperCase(),
                apiHostname.toLowerCase(),
                path,
                params);

        Mac mac = Mac.getInstance("HmacSHA1");
        mac.init(new SecretKeySpec(secretKey.getBytes(StandardCharsets.UTF_8), "HmacSHA1"));
        byte[] raw = mac.doFinal(canon.getBytes(StandardCharsets.UTF_8));

        StringBuilder hex = new StringBuilder(raw.length * 2);
        for (byte b : raw) {
            hex.append(String.format("%02x", b));
        }

        String credentials = integrationKey + ":" + hex;
        return "Basic " + Base64.getEncoder().encodeToString(credentials.getBytes(StandardCharsets.UTF_8));
    }

    // ── Utilities ─────────────────────────────────────────────────────────────

    /** Sorts by key, percent-encodes both key and value (RFC 3986, spaces as %20). */
    private String encodeParams(Map<String, String> params) {
        return params.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .map(e -> rfc3986(e.getKey()) + "=" + rfc3986(e.getValue()))
                .collect(Collectors.joining("&"));
    }

    private String rfc3986(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private String now() {
        return ZonedDateTime.now(ZoneOffset.UTC).format(RFC_2822);
    }

    private void assertOk(JsonNode body, String context) {
        if (!"OK".equals(body.path("stat").asText())) {
            String message = body.path("message").asText();
            log.error("{} returned non-OK stat: {}", context, message);
            throw new RuntimeException(context + " failed: " + message);
        }
    }
}
