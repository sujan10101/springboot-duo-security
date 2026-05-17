package com.example.duosecurity.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Sample protected endpoints — all require a valid AUTHENTICATED JWT.
 * Use: Authorization: Bearer <accessToken>
 */
@RestController
@RequestMapping("/api")
public class ApiController {

    /** Any authenticated user. */
    @GetMapping("/hello")
    public ResponseEntity<Map<String, String>> hello(Authentication auth) {
        return ResponseEntity.ok(Map.of(
                "message", "Hello, " + auth.getName() + "!",
                "status",  "authenticated"
        ));
    }

    /** Any authenticated user — shows their authorities. */
    @GetMapping("/profile")
    public ResponseEntity<Map<String, Object>> profile(Authentication auth) {
        return ResponseEntity.ok(Map.of(
                "username",      auth.getName(),
                "authorities",   auth.getAuthorities().toString(),
                "authenticated", auth.isAuthenticated()
        ));
    }

    /** ROLE_ADMIN only. */
    @GetMapping("/admin")
    @PreAuthorize("hasAuthority('ROLE_ADMIN')")
    public ResponseEntity<Map<String, String>> admin() {
        return ResponseEntity.ok(Map.of("message", "Admin area — restricted access"));
    }
}
