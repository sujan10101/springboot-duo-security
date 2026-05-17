package com.example.duosecurity.init;

import com.example.duosecurity.entity.User;
import com.example.duosecurity.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.util.Set;

@Component
@RequiredArgsConstructor
@Slf4j
public class DataInitializer implements CommandLineRunner {

    private final UserRepository  userRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public void run(String... args) {
        if (userRepository.count() > 0) return;

        userRepository.save(new User(
                "alice",
                passwordEncoder.encode("password123"),
                "alice@example.com",
                Set.of("ROLE_USER")
        ));

        userRepository.save(new User(
                "admin",
                passwordEncoder.encode("admin123"),
                "admin@example.com",
                Set.of("ROLE_USER", "ROLE_ADMIN")
        ));

        log.info("Seeded users: alice/password123 (ROLE_USER), admin/admin123 (ROLE_USER, ROLE_ADMIN)");
    }
}
