package collector

import (
	"context"
	"sync"

	"github.com/prometheus/client_golang/prometheus"
	"go.uber.org/zap"
)

// Collector interface for metric collection
type Collector interface {
	// Name returns the collector name
	Name() string

	// Collect gathers metrics
	Collect(ctx context.Context) error

	// Describe sends metric descriptors to the channel
	Describe(ch chan<- *prometheus.Desc)

	// Collect sends metrics to the channel
	CollectMetrics(ch chan<- prometheus.Metric)
}

// Manager manages all collectors
type Manager struct {
	collectors []Collector
	logger     *zap.Logger
	mu         sync.RWMutex
}

// NewManager creates a new collector manager
func NewManager(logger *zap.Logger) *Manager {
	return &Manager{
		collectors: make([]Collector, 0),
		logger:     logger,
	}
}

// Register adds a collector to the manager
func (m *Manager) Register(collector Collector) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.collectors = append(m.collectors, collector)
	m.logger.Info("registered collector", zap.String("name", collector.Name()))
}

// CollectAll runs all collectors
func (m *Manager) CollectAll(ctx context.Context) error {
	m.mu.RLock()
	collectors := m.collectors
	m.mu.RUnlock()

	var wg sync.WaitGroup
	errCh := make(chan error, len(collectors))

	for _, c := range collectors {
		wg.Add(1)
		go func(collector Collector) {
			defer wg.Done()
			if err := collector.Collect(ctx); err != nil {
				m.logger.Error("collector failed",
					zap.String("name", collector.Name()),
					zap.Error(err))
				errCh <- err
			}
		}(c)
	}

	wg.Wait()
	close(errCh)

	// Return first error if any
	for err := range errCh {
		return err
	}

	return nil
}

// Describe implements prometheus.Collector
func (m *Manager) Describe(ch chan<- *prometheus.Desc) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	for _, c := range m.collectors {
		c.Describe(ch)
	}
}

// Collect implements prometheus.Collector
func (m *Manager) Collect(ch chan<- prometheus.Metric) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	for _, c := range m.collectors {
		c.CollectMetrics(ch)
	}
}
