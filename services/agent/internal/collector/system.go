package collector

import (
	"context"
	"fmt"
	"runtime"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"go.uber.org/zap"
)

// SystemCollector collects system-level metrics
type SystemCollector struct {
	logger *zap.Logger
	nodeID string

	// CPU metrics
	cpuPercent *prometheus.GaugeVec

	// Memory metrics
	memoryTotal     prometheus.Gauge
	memoryAvailable prometheus.Gauge
	memoryUsed      prometheus.Gauge
	memoryPercent   prometheus.Gauge

	// Disk metrics
	diskTotal   *prometheus.GaugeVec
	diskUsed    *prometheus.GaugeVec
	diskPercent *prometheus.GaugeVec

	// Network metrics
	networkBytesRecv *prometheus.GaugeVec
	networkBytesSent *prometheus.GaugeVec

	// System info
	uptime prometheus.Gauge
}

// NewSystemCollector creates a new system metrics collector
func NewSystemCollector(nodeID string, logger *zap.Logger) *SystemCollector {
	return &SystemCollector{
		logger: logger,
		nodeID: nodeID,

		cpuPercent: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "cpu_percent",
				Help:      "CPU usage percentage",
			},
			[]string{"node", "cpu"},
		),

		memoryTotal: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "memory_bytes_total",
				Help:      "Total memory in bytes",
			},
		),

		memoryAvailable: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "memory_bytes_available",
				Help:      "Available memory in bytes",
			},
		),

		memoryUsed: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "memory_bytes_used",
				Help:      "Used memory in bytes",
			},
		),

		memoryPercent: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "memory_percent",
				Help:      "Memory usage percentage",
			},
		),

		diskTotal: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "disk_bytes_total",
				Help:      "Total disk space in bytes",
			},
			[]string{"node", "device", "mountpoint"},
		),

		diskUsed: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "disk_bytes_used",
				Help:      "Used disk space in bytes",
			},
			[]string{"node", "device", "mountpoint"},
		),

		diskPercent: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "disk_percent",
				Help:      "Disk usage percentage",
			},
			[]string{"node", "device", "mountpoint"},
		),

		networkBytesRecv: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "network_bytes_recv",
				Help:      "Network bytes received",
			},
			[]string{"node", "interface"},
		),

		networkBytesSent: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "network_bytes_sent",
				Help:      "Network bytes sent",
			},
			[]string{"node", "interface"},
		),

		uptime: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "uptime_seconds",
				Help:      "Node uptime in seconds",
			},
		),
	}
}

// Name returns the collector name
func (c *SystemCollector) Name() string {
	return "system"
}

// Collect gathers system metrics
func (c *SystemCollector) Collect(_ context.Context) error {
	// Collect CPU metrics
	if err := c.collectCPU(); err != nil {
		c.logger.Warn("failed to collect CPU metrics", zap.Error(err))
	}

	// Collect memory metrics
	if err := c.collectMemory(); err != nil {
		c.logger.Warn("failed to collect memory metrics", zap.Error(err))
	}

	// Collect disk metrics
	if err := c.collectDisk(); err != nil {
		c.logger.Warn("failed to collect disk metrics", zap.Error(err))
	}

	// Collect network metrics
	if err := c.collectNetwork(); err != nil {
		c.logger.Warn("failed to collect network metrics", zap.Error(err))
	}

	// Update uptime
	c.uptime.Set(time.Since(time.Now().Add(-10 * time.Second)).Seconds())

	return nil
}

func (c *SystemCollector) collectCPU() error {
	// Simple CPU usage - for demo purposes
	// In production, use github.com/shirou/gopsutil/v3/cpu
	numCPU := runtime.NumCPU()
	for i := 0; i < numCPU; i++ {
		// Mock CPU usage between 10-60%
		usage := float64(10 + (i * 10 % 50))
		c.cpuPercent.WithLabelValues(c.nodeID, fmt.Sprintf("cpu%d", i)).Set(usage)
	}
	return nil
}

func (c *SystemCollector) collectMemory() error {
	// Get memory stats from runtime
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	// Mock total and available memory (in production use gopsutil)
	totalMemory := float64(16 * 1024 * 1024 * 1024) // 16GB
	usedMemory := float64(m.Alloc)
	availableMemory := totalMemory - usedMemory

	c.memoryTotal.Set(totalMemory)
	c.memoryUsed.Set(usedMemory)
	c.memoryAvailable.Set(availableMemory)
	c.memoryPercent.Set((usedMemory / totalMemory) * 100)

	return nil
}

func (c *SystemCollector) collectDisk() error {
	// Mock disk usage (in production use gopsutil)
	c.diskTotal.WithLabelValues(c.nodeID, "/dev/sda1", "/").Set(500 * 1024 * 1024 * 1024)  // 500GB
	c.diskUsed.WithLabelValues(c.nodeID, "/dev/sda1", "/").Set(300 * 1024 * 1024 * 1024)   // 300GB
	c.diskPercent.WithLabelValues(c.nodeID, "/dev/sda1", "/").Set(60)

	return nil
}

func (c *SystemCollector) collectNetwork() error {
	// Mock network stats (in production use gopsutil)
	c.networkBytesRecv.WithLabelValues(c.nodeID, "eth0").Set(1024 * 1024 * 1024) // 1GB
	c.networkBytesSent.WithLabelValues(c.nodeID, "eth0").Set(512 * 1024 * 1024)  // 512MB

	return nil
}

// Describe implements prometheus.Collector
func (c *SystemCollector) Describe(ch chan<- *prometheus.Desc) {
	c.cpuPercent.Describe(ch)
	ch <- c.memoryTotal.Desc()
	ch <- c.memoryAvailable.Desc()
	ch <- c.memoryUsed.Desc()
	ch <- c.memoryPercent.Desc()
	c.diskTotal.Describe(ch)
	c.diskUsed.Describe(ch)
	c.diskPercent.Describe(ch)
	c.networkBytesRecv.Describe(ch)
	c.networkBytesSent.Describe(ch)
	ch <- c.uptime.Desc()
}

// CollectMetrics implements prometheus.Collector
func (c *SystemCollector) CollectMetrics(ch chan<- prometheus.Metric) {
	c.cpuPercent.Collect(ch)
	ch <- c.memoryTotal
	ch <- c.memoryAvailable
	ch <- c.memoryUsed
	ch <- c.memoryPercent
	c.diskTotal.Collect(ch)
	c.diskUsed.Collect(ch)
	c.diskPercent.Collect(ch)
	c.networkBytesRecv.Collect(ch)
	c.networkBytesSent.Collect(ch)
	ch <- c.uptime
}
