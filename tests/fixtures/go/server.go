package server

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type Config struct {
	Host    string
	Port    int
	Timeout time.Duration
}

type Server struct {
	config Config
	mux    *http.ServeMux
	client *http.Client
}

func New(cfg Config) *Server {
	return &Server{
		config: cfg,
		mux:    http.NewServeMux(),
		client: &http.Client{Timeout: cfg.Timeout},
	}
}

func (s *Server) RegisterRoute(pattern string, handler http.HandlerFunc) {
	s.mux.HandleFunc(pattern, handler)
}

func (s *Server) Start(ctx context.Context) error {
	addr := fmt.Sprintf("%s:%d", s.config.Host, s.config.Port)
	srv := &http.Server{Addr: addr, Handler: s.mux}
	go func() {
		<-ctx.Done()
		srv.Shutdown(context.Background())
	}()
	return srv.ListenAndServe()
}

func (s *Server) writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

type HealthResponse struct {
	Status string `json:"status"`
	Uptime string `json:"uptime"`
}

func healthHandler(start time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		resp := HealthResponse{
			Status: "ok",
			Uptime: time.Since(start).String(),
		}
		json.NewEncoder(w).Encode(resp)
	}
}
