package com.example.duosecurity.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.util.Collection;
import java.util.Date;
import java.util.HexFormat;
import java.util.List;

@Service
public class JwtService {

    private static final String CLAIM_TYPE     = "type";
    private static final String CLAIM_DUO_TXID = "duo_txid";
    private static final String CLAIM_ROLES    = "roles";
    private static final String TYPE_PENDING   = "PENDING_MFA";
    private static final String TYPE_AUTH      = "AUTHENTICATED";

    @Value("${app.jwt.secret}")
    private String jwtSecret;

    @Value("${app.jwt.expiration}")
    private long jwtExpiration;

    @Value("${app.jwt.mfa-pending-expiration}")
    private long mfaPendingExpiration;

    // ── Token generation ──────────────────────────────────────────────────────

    /**
     * Short-lived token that carries the Duo txid through the MFA polling step.
     * Cannot be used to access protected endpoints.
     */
    public String generatePendingToken(String username, String duoTxid) {
        return Jwts.builder()
                .subject(username)
                .claim(CLAIM_TYPE, TYPE_PENDING)
                .claim(CLAIM_DUO_TXID, duoTxid)
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + mfaPendingExpiration))
                .signWith(signingKey())
                .compact();
    }

    /** Full auth token issued only after Duo approval. */
    public String generateAuthToken(String username, Collection<String> roles) {
        return Jwts.builder()
                .subject(username)
                .claim(CLAIM_TYPE, TYPE_AUTH)
                .claim(CLAIM_ROLES, roles)
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + jwtExpiration))
                .signWith(signingKey())
                .compact();
    }

    // ── Validation ────────────────────────────────────────────────────────────

    /** Returns true only for fully-authenticated tokens (Duo already approved). */
    public boolean isValidAuthToken(String token) {
        try {
            Claims claims = allClaims(token);
            return TYPE_AUTH.equals(claims.get(CLAIM_TYPE, String.class));
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }

    /** Returns true only for pending-MFA tokens (Duo not yet checked). */
    public boolean isValidPendingToken(String token) {
        try {
            Claims claims = allClaims(token);
            return TYPE_PENDING.equals(claims.get(CLAIM_TYPE, String.class));
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }

    // ── Extraction ────────────────────────────────────────────────────────────

    public String extractUsername(String token) {
        return allClaims(token).getSubject();
    }

    public String extractDuoTxid(String token) {
        return allClaims(token).get(CLAIM_DUO_TXID, String.class);
    }

    @SuppressWarnings("unchecked")
    public List<String> extractRoles(String token) {
        return allClaims(token).get(CLAIM_ROLES, List.class);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private Claims allClaims(String token) {
        return Jwts.parser()
                .verifyWith(signingKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    private SecretKey signingKey() {
        byte[] keyBytes = HexFormat.of().parseHex(jwtSecret);
        return Keys.hmacShaKeyFor(keyBytes);
    }
}
