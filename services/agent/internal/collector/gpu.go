package collector

import (
	"context"
	"fmt"

	"github.com/NVIDIA/go-nvml/pkg/nvml"
	"github.com/prometheus/client_golang/prometheus"
	"go.uber.org/zap"
)

// GPUCollector collects GPU metrics using NVIDIA NVML
type GPUCollector struct {
	logger  *zap.Logger
	nodeID  string
	enabled bool

	// GPU metrics
	gpuUtilization   *prometheus.GaugeVec
	gpuMemoryUsed    *prometheus.GaugeVec
	gpuMemoryTotal   *prometheus.GaugeVec
	gpuMemoryPercent *prometheus.GaugeVec
	gpuTemperature   *prometheus.GaugeVec
	gpuPowerUsage    *prometheus.GaugeVec
	gpuFanSpeed      *prometheus.GaugeVec
}

// NewGPUCollector creates a new GPU metrics collector
func NewGPUCollector(nodeID string, enabled bool, logger *zap.Logger) *GPUCollector {
	return &GPUCollector{
		logger:  logger,
		nodeID:  nodeID,
		enabled: enabled,

		gpuUtilization: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "gpu_utilization_percent",
				Help:      "GPU utilization percentage",
			},
			[]string{"node", "gpu", "sku"},
		),

		gpuMemoryUsed: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "gpu_memory_bytes_used",
				Help:      "GPU memory used in bytes",
			},
			[]string{"node", "gpu", "sku"},
		),

		gpuMemoryTotal: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "gpu_memory_bytes_total",
				Help:      "GPU memory total in bytes",
			},
			[]string{"node", "gpu", "sku"},
		),

		gpuMemoryPercent: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "gpu_memory_percent",
				Help:      "GPU memory usage percentage",
			},
			[]string{"node", "gpu", "sku"},
		),

		gpuTemperature: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "gpu_temperature_celsius",
				Help:      "GPU temperature in Celsius",
			},
			[]string{"node", "gpu", "sku"},
		),

		gpuPowerUsage: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "gpu_power_watts",
				Help:      "GPU power usage in watts",
			},
			[]string{"node", "gpu", "sku"},
		),

		gpuFanSpeed: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "sentinel_node",
				Name:      "gpu_fan_speed_percent",
				Help:      "GPU fan speed percentage",
			},
			[]string{"node", "gpu", "sku"},
		),
	}
}

// Name returns the collector name
func (c *GPUCollector) Name() string {
	return "gpu"
}

// Collect gathers GPU metrics
func (c *GPUCollector) Collect(_ context.Context) error {
	if !c.enabled {
		return nil
	}

	// Initialize NVML
	ret := nvml.Init()
	if ret != nvml.SUCCESS {
		c.logger.Debug("NVML not available, skipping GPU metrics",
			zap.String("error", nvml.ErrorString(ret)))
		return nil
	}
	defer func() {
		if ret := nvml.Shutdown(); ret != nvml.SUCCESS {
			c.logger.Warn("failed to shutdown NVML",
				zap.String("error", nvml.ErrorString(ret)))
		}
	}()

	// Get device count
	count, ret := nvml.DeviceGetCount()
	if ret != nvml.SUCCESS {
		return fmt.Errorf("failed to get device count: %s", nvml.ErrorString(ret))
	}

	// Collect metrics for each GPU
	for i := 0; i < count; i++ {
		if err := c.collectDeviceMetrics(i); err != nil {
			c.logger.Warn("failed to collect GPU metrics",
				zap.Int("gpu", i),
				zap.Error(err))
		}
	}

	return nil
}

func (c *GPUCollector) collectDeviceMetrics(index int) error {
	device, ret := nvml.DeviceGetHandleByIndex(index)
	if ret != nvml.SUCCESS {
		return fmt.Errorf("failed to get device handle: %s", nvml.ErrorString(ret))
	}

	gpuID := fmt.Sprintf("gpu%d", index)

	// Get device name (SKU)
	name, ret := device.GetName()
	if ret != nvml.SUCCESS {
		name = "unknown"
	}

	// GPU Utilization
	utilization, ret := device.GetUtilizationRates()
	if ret == nvml.SUCCESS {
		c.gpuUtilization.WithLabelValues(c.nodeID, gpuID, name).Set(float64(utilization.Gpu))
	}

	// Memory Info
	memInfo, ret := device.GetMemoryInfo()
	if ret == nvml.SUCCESS {
		c.gpuMemoryUsed.WithLabelValues(c.nodeID, gpuID, name).Set(float64(memInfo.Used))
		c.gpuMemoryTotal.WithLabelValues(c.nodeID, gpuID, name).Set(float64(memInfo.Total))
		memPercent := (float64(memInfo.Used) / float64(memInfo.Total)) * 100
		c.gpuMemoryPercent.WithLabelValues(c.nodeID, gpuID, name).Set(memPercent)
	}

	// Temperature
	temp, ret := device.GetTemperature(nvml.TEMPERATURE_GPU)
	if ret == nvml.SUCCESS {
		c.gpuTemperature.WithLabelValues(c.nodeID, gpuID, name).Set(float64(temp))
	}

	// Power Usage
	power, ret := device.GetPowerUsage()
	if ret == nvml.SUCCESS {
		// Convert milliwatts to watts
		c.gpuPowerUsage.WithLabelValues(c.nodeID, gpuID, name).Set(float64(power) / 1000.0)
	}

	// Fan Speed
	fanSpeed, ret := device.GetFanSpeed()
	if ret == nvml.SUCCESS {
		c.gpuFanSpeed.WithLabelValues(c.nodeID, gpuID, name).Set(float64(fanSpeed))
	}

	return nil
}

// Describe implements prometheus.Collector
func (c *GPUCollector) Describe(ch chan<- *prometheus.Desc) {
	if !c.enabled {
		return
	}
	c.gpuUtilization.Describe(ch)
	c.gpuMemoryUsed.Describe(ch)
	c.gpuMemoryTotal.Describe(ch)
	c.gpuMemoryPercent.Describe(ch)
	c.gpuTemperature.Describe(ch)
	c.gpuPowerUsage.Describe(ch)
	c.gpuFanSpeed.Describe(ch)
}

// CollectMetrics implements prometheus.Collector
func (c *GPUCollector) CollectMetrics(ch chan<- prometheus.Metric) {
	if !c.enabled {
		return
	}
	c.gpuUtilization.Collect(ch)
	c.gpuMemoryUsed.Collect(ch)
	c.gpuMemoryTotal.Collect(ch)
	c.gpuMemoryPercent.Collect(ch)
	c.gpuTemperature.Collect(ch)
	c.gpuPowerUsage.Collect(ch)
	c.gpuFanSpeed.Collect(ch)
}
