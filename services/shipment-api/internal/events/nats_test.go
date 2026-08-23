package events

import (
	"context"
	"errors"
	"testing"
	"time"
)

type fakeNatsConnection struct {
	connected bool
	rttErr    error
}

func (f *fakeNatsConnection) IsConnected() bool           { return f.connected }
func (f *fakeNatsConnection) RTT() (time.Duration, error) { return 0, f.rttErr }
func (f *fakeNatsConnection) Drain() error                { return nil }
func (f *fakeNatsConnection) Close()                      {}

func TestNatsPublisherPingReturnsRTTError(t *testing.T) {
	want := errors.New("round-trip failed")
	publisher := &NatsPublisher{nc: &fakeNatsConnection{connected: true, rttErr: want}}

	if got := publisher.Ping(context.Background()); !errors.Is(got, want) {
		t.Fatalf("Ping() error = %v, want %v", got, want)
	}
}
