package config

import (
	"fmt"

	"github.com/spf13/viper"
)

// Config represents the agent configuration
type Config struct {
	NodeID      string      `mapstructure:"node_id"`
	MetricsPort int         `mapstructure:"metrics_port"`
	ControlAPI  string      `mapstructure:"control_api"`
	TLS         TLSConfig   `mapstructure:"tls"`
	Collectors  []string    `mapstructure:"collectors"`
	Log         LogConfig   `mapstructure:"log"`
	GPU         GPUConfig   `mapstructure:"gpu"`
}

// TLSConfig holds TLS certificate configuration
type TLSConfig struct {
	Enabled bool   `mapstructure:"enabled"`
	Cert    string `mapstructure:"cert"`
	Key     string `mapstructure:"key"`
	CA      string `mapstructure:"ca"`
}

// LogConfig holds logging configuration
type LogConfig struct {
	Level  string `mapstructure:"level"`
	Format string `mapstructure:"format"` // json or text
}

// GPUConfig holds GPU monitoring configuration
type GPUConfig struct {
	Enabled bool `mapstructure:"enabled"`
}

// Load loads configuration from file and environment
func Load(cfgFile string) (*Config, error) {
	// Set defaults
	viper.SetDefault("node_id", "node-local")
	viper.SetDefault("metrics_port", 9100)
	viper.SetDefault("control_api", "http://localhost:8000")
	viper.SetDefault("tls.enabled", false)
	viper.SetDefault("collectors", []string{"cpu", "memory", "disk", "network"})
	viper.SetDefault("log.level", "info")
	viper.SetDefault("log.format", "json")
	viper.SetDefault("gpu.enabled", true)

	// Read from config file if provided
	if cfgFile != "" {
		viper.SetConfigFile(cfgFile)
	} else {
		viper.SetConfigName("config")
		viper.SetConfigType("yaml")
		viper.AddConfigPath("/etc/sentinel")
		viper.AddConfigPath("$HOME/.sentinel")
		viper.AddConfigPath(".")
	}

	// Read from environment variables
	viper.SetEnvPrefix("SENTINEL")
	viper.AutomaticEnv()

	// Read config file (not mandatory)
	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, fmt.Errorf("failed to read config: %w", err)
		}
	}

	var cfg Config
	if err := viper.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	return &cfg, nil
}
