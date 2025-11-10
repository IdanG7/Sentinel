package metrics

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

// Server is the HTTP server for metrics exposure
type Server struct {
	port       int
	server     *http.Server
	registry   *prometheus.Registry
	logger     *zap.Logger
}

// NewServer creates a new metrics server
func NewServer(port int, registry *prometheus.Registry, logger *zap.Logger) *Server {
	return &Server{
		port:     port,
		registry: registry,
		logger:   logger,
	}
}

// Start starts the metrics HTTP server
func (s *Server) Start(ctx context.Context) error {
	mux := http.NewServeMux()

	// Metrics endpoint
	mux.Handle("/metrics", promhttp.HandlerFor(
		s.registry,
		promhttp.HandlerOpts{
			EnableOpenMetrics: true,
		},
	))

	// Health check endpoint
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy"}`))
	})

	// Readiness endpoint
	mux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ready"}`))
	})

	s.server = &http.Server{
		Addr:         fmt.Sprintf(":%d", s.port),
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	s.logger.Info("starting metrics server", zap.Int("port", s.port))

	go func() {
		if err := s.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			s.logger.Error("metrics server error", zap.Error(err))
		}
	}()

	// Wait for context cancellation
	<-ctx.Done()
	return s.Shutdown()
}

// Shutdown gracefully shuts down the server
func (s *Server) Shutdown() error {
	if s.server == nil {
		return nil
	}

	s.logger.Info("shutting down metrics server")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	return s.server.Shutdown(ctx)
}
