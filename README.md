# Spring Boot + Duo MFA + JWT

A Spring Boot REST API that implements two-factor authentication using [Duo Security](https://duo.com/) and stateless JWT sessions.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Spring Boot 3.2.5 (Java 17) |
| Security | Spring Security + JWT (jjwt 0.12.5) |
| MFA | Duo Auth API (push & passcode) |
| Database | PostgreSQL (Spring Data JPA) |
| Build | Maven |

## Authentication Flow

```
POST /auth/login           → validate password → trigger Duo push → return pendingToken
POST /auth/mfa/verify      → poll Duo for push approval          → return JWT (or 202 waiting)
POST /auth/mfa/passcode    → submit TOTP / SMS passcode          → return JWT
GET  /auth/preauth         → inspect Duo enrollment status for a user
```

1. Client sends username + password to `/auth/login`.
2. On success, the server sends a Duo push to the enrolled device and returns a short-lived `pendingToken` (30 min).
3. Client polls `/auth/mfa/verify` with that token until Duo approves (HTTP 200) or it gets an error.
4. Alternatively the client submits a passcode via `/auth/mfa/passcode`.
5. On MFA success the server issues a full JWT (24 h) usable on all protected endpoints.

## Prerequisites

- Java 17+
- Maven 3.8+
- PostgreSQL running locally on port `5432`
- A [Duo Auth API](https://duo.com/docs/authapi) application (Admin Panel → Applications → Protect an Application → Auth API)

## Configuration

Copy `application.properties` and fill in your values — **never commit real secrets**:

```properties
# PostgreSQL
spring.datasource.url=jdbc:postgresql://localhost:5432/duo_security_db
spring.datasource.username=postgres
spring.datasource.password=YOUR_DB_PASSWORD

# JWT (64-char hex, 256-bit HS256 key)
app.jwt.secret=CHANGE_ME

# Duo Auth API credentials (from Admin Panel)
duo.api-hostname=api-XXXXXXXX.duosecurity.com
duo.integration-key=DIXXXXXXXXXXXXXXXXXXXXXXXX
duo.secret-key=CHANGE_ME

# Set true to skip real Duo calls during local dev (passcode "000000" always accepted)
duo.mock-enabled=false
```

> Prefer environment variables or a secrets manager in production instead of properties files.

## Running Locally

```bash
# 1. Create the database
psql -U postgres -c "CREATE DATABASE duo_security_db;"

# 2. Build and run
./mvnw spring-boot:run
```

The server starts on `http://localhost:8080`. A default `admin` user is seeded by `DataInitializer` on first boot.

## API Endpoints

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | None | Step 1 — password check + Duo push |
| `POST` | `/auth/mfa/verify` | None | Step 2a — poll for push approval |
| `POST` | `/auth/mfa/passcode` | None | Step 2b — submit TOTP/SMS passcode |
| `GET` | `/auth/preauth` | None | Check Duo enrollment for a user |

### Protected

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/**` | JWT Bearer | Example protected resource |

### Example Request Sequence

```bash
# Step 1 — login
curl -s -X POST http://localhost:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"password123"}' | jq .

# Step 2 — poll for push (repeat until status != "waiting")
curl -s -X POST http://localhost:8080/auth/mfa/verify \
  -H 'Content-Type: application/json' \
  -d '{"pendingToken":"<token from step 1>"}' | jq .

# Use the JWT
curl -s http://localhost:8080/api/hello \
  -H 'Authorization: Bearer <jwt from step 2>'
```

## Mock Mode

Set `duo.mock-enabled=true` in `application.properties` to skip real Duo calls during development. In mock mode, passcode `000000` is always accepted and push resolves immediately.

## Project Structure

```
src/main/java/com/example/duosecurity/
├── config/          # Spring Security configuration
├── controller/      # AuthController, ApiController
├── dto/             # Request/response DTOs
├── entity/          # User entity
├── exception/       # Global exception handler
├── init/            # DataInitializer (seeds default users)
├── repository/      # UserRepository
├── security/        # JwtService, JwtAuthFilter
└── service/         # AuthService, DuoAuthService, DuoApiClient
```

## License

MIT
