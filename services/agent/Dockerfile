# Sentinel Node Agent - Dockerfile
FROM golang:1.21-alpine as builder

WORKDIR /build

# Install build dependencies
RUN apk add --no-cache git make

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s -X main.version=0.1.0" \
    -o sentinel-agent \
    cmd/agent/main.go

# Final stage
FROM alpine:3.22

WORKDIR /app

# Install runtime dependencies
RUN apk add --no-cache ca-certificates curl

# Copy binary from builder
COPY --from=builder /build/sentinel-agent /usr/local/bin/sentinel-agent

# Create non-root user
RUN addgroup -g 1000 sentinel && \
    adduser -D -u 1000 -G sentinel sentinel && \
    chown -R sentinel:sentinel /app

USER sentinel

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9100/metrics || exit 1

# Expose metrics port
EXPOSE 9100

# Run agent
ENTRYPOINT ["/usr/local/bin/sentinel-agent"]
CMD ["--config", "/etc/sentinel/config.yaml"]
