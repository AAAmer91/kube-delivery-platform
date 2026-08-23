package main

import (
	"errors"
	"testing"
	"time"
)

func TestRetryConnectRecoversFromStartupRace(t *testing.T) {
	attempts := 0
	value, err := retryConnect("test dependency", 3, 0*time.Millisecond, func() (string, error) {
		attempts++
		if attempts < 3 {
			return "", errors.New("not ready")
		}
		return "connected", nil
	})

	if err != nil {
		t.Fatalf("expected retry to recover, got %v", err)
	}
	if value != "connected" || attempts != 3 {
		t.Fatalf("expected third attempt to connect, value=%q attempts=%d", value, attempts)
	}
}

func TestRetryConnectReturnsLastError(t *testing.T) {
	_, err := retryConnect("test dependency", 2, 0*time.Millisecond, func() (string, error) {
		return "", errors.New("still unavailable")
	})

	if err == nil {
		t.Fatal("expected exhausted retry error")
	}
}
