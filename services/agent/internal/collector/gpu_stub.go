//go:build !cgo
// +build !cgo

package collector

import (
	"context"

	"github.com/prometheus/client_golang/prometheus"
	"go.uber.org/zap"
)

// GPUCollector is a stub when CGO is disabled
type GPUCollector struct {
	logger  *zap.Logger
	nodeID  string
	enabled bool
}

// NewGPUCollector creates a stub GPU collector
func NewGPUCollector(nodeID string, enabled bool, logger *zap.Logger) *GPUCollector {
	if enabled {
		logger.Warn("GPU metrics disabled: built without CGO support")
	}
	return &GPUCollector{
		logger:  logger,
		nodeID:  nodeID,
		enabled: false, // Always disabled without CGO
	}
}

// Name returns the collector name
func (c *GPUCollector) Name() string {
	return "gpu"
}

// Collect is a no-op when CGO is disabled
func (c *GPUCollector) Collect(_ context.Context) error {
	return nil
}

// Describe is a no-op when CGO is disabled
func (c *GPUCollector) Describe(_ chan<- *prometheus.Desc) {
}

// CollectMetrics is a no-op when CGO is disabled
func (c *GPUCollector) CollectMetrics(_ chan<- prometheus.Metric) {
}
