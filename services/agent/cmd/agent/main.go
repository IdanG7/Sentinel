package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/spf13/cobra"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"

	"github.com/sentinel/agent/internal/collector"
	"github.com/sentinel/agent/internal/config"
	"github.com/sentinel/agent/internal/metrics"
)

var (
	version = "0.1.0"
	cfgFile string
)

var rootCmd = &cobra.Command{
	Use:   "sentinel-agent",
	Short: "Sentinel Node Agent - Metrics collector and action executor",
	Long: `Sentinel Node Agent collects system and GPU metrics,
exposes Prometheus endpoints, and executes scoped node actions.`,
	Version: version,
	RunE:    run,
}

func init() {
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default: /etc/sentinel/config.yaml)")
}

func main() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func run(cmd *cobra.Command, args []string) error {
	// Load configuration
	cfg, err := config.Load(cfgFile)
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}

	// Initialize logger
	logger, err := initLogger(cfg.Log.Level, cfg.Log.Format)
	if err != nil {
		return fmt.Errorf("failed to initialize logger: %w", err)
	}
	defer func() {
		_ = logger.Sync() // Ignore sync errors on shutdown
	}()

	logger.Info("starting Sentinel Agent",
		zap.String("version", version),
		zap.String("node_id", cfg.NodeID),
		zap.Int("metrics_port", cfg.MetricsPort),
	)

	// Create context for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Setup signal handling
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)

	// Create Prometheus registry
	registry := prometheus.NewRegistry()

	// Create collector manager
	collectorMgr := collector.NewManager(logger)

	// Register system collector
	systemCollector := collector.NewSystemCollector(cfg.NodeID, logger)
	collectorMgr.Register(systemCollector)

	// Register GPU collector if enabled
	if cfg.GPU.Enabled {
		gpuCollector := collector.NewGPUCollector(cfg.NodeID, cfg.GPU.Enabled, logger)
		collectorMgr.Register(gpuCollector)
	}

	// Register collector manager with Prometheus
	if err := registry.Register(collectorMgr); err != nil {
		return fmt.Errorf("failed to register collector: %w", err)
	}

	// Create metrics server
	metricsServer := metrics.NewServer(cfg.MetricsPort, registry, logger)

	// Start metrics server in background
	go func() {
		if err := metricsServer.Start(ctx); err != nil {
			logger.Error("metrics server failed", zap.Error(err))
			cancel()
		}
	}()

	// Start collection loop
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	logger.Info("agent started successfully")

	// Main loop
	for {
		select {
		case <-ticker.C:
			if err := collectorMgr.CollectAll(ctx); err != nil {
				logger.Error("collection failed", zap.Error(err))
			}

		case sig := <-sigCh:
			logger.Info("received shutdown signal", zap.String("signal", sig.String()))
			cancel()
			// Shutdown metrics server
			if err := metricsServer.Shutdown(); err != nil {
				logger.Error("failed to shutdown metrics server", zap.Error(err))
			}
			return nil

		case <-ctx.Done():
			logger.Info("shutting down agent")
			// Shutdown metrics server
			if err := metricsServer.Shutdown(); err != nil {
				logger.Error("failed to shutdown metrics server", zap.Error(err))
			}
			return nil
		}
	}
}

func initLogger(level, format string) (*zap.Logger, error) {
	// Parse log level
	var zapLevel zapcore.Level
	if err := zapLevel.UnmarshalText([]byte(level)); err != nil {
		zapLevel = zapcore.InfoLevel
	}

	// Create config
	var cfg zap.Config
	if format == "json" {
		cfg = zap.NewProductionConfig()
	} else {
		cfg = zap.NewDevelopmentConfig()
	}

	cfg.Level = zap.NewAtomicLevelAt(zapLevel)

	// Build logger
	return cfg.Build()
}
