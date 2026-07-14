using System;

namespace Valera.VrGateway.Contracts
{
    public static class WireValues
    {
        public const string SchemaVersion = "0.1";

        public const string SessionStart = "session.start";
        public const string SessionStop = "session.stop";
        public const string ModeSet = "mode.set";
        public const string HeadPose = "head.pose";
        public const string HeadRecenter = "head.recenter";
        public const string EmergencyStop = "emergency_stop";

        public const string GatewayState = "gateway.state";
        public const string NeckTarget = "neck.target";
        public const string SafetyStop = "safety.stop";
        public const string CommandRejected = "command.rejected";
    }

    [Serializable]
    public readonly struct Correlation : IEquatable<Correlation>
    {
        public static readonly Correlation Unavailable = new Correlation();

        public readonly bool IsAvailable;
        public readonly string SessionId;
        public readonly long Sequence;

        public Correlation(string sessionId, long sequence)
        {
            if (string.IsNullOrWhiteSpace(sessionId)) throw new ArgumentException("session_id must be non-empty and non-whitespace.", nameof(sessionId));
            if (sequence < 1) throw new ArgumentOutOfRangeException(nameof(sequence), "sequence must be at least 1.");
            IsAvailable = true;
            SessionId = sessionId;
            Sequence = sequence;
        }

        public bool Equals(Correlation other)
        {
            return IsAvailable == other.IsAvailable && SessionId == other.SessionId && Sequence == other.Sequence;
        }

        public override bool Equals(object obj)
        {
            return obj is Correlation other && Equals(other);
        }

        public override int GetHashCode()
        {
            if (!IsAvailable) return 0;
            return SessionId.GetHashCode() ^ Sequence.GetHashCode();
        }

        public override string ToString()
        {
            return IsAvailable ? $"{SessionId}:{Sequence}" : "unavailable";
        }
    }

    [Serializable]
    public sealed class CommandEnvelopeDto
    {
        public string schema_version;
        public string command;
        public string session_id;
        public long sequence;
        public long timestamp_ms;
        public PayloadDto payload;
    }

    [Serializable] public sealed class SessionStartCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public SessionStartPayloadDto payload; }
    [Serializable] public sealed class SessionStopCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public EmptyPayloadDto payload; }
    [Serializable] public sealed class ModeSetCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public ModeSetPayloadDto payload; }
    [Serializable] public sealed class HeadPoseCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public HeadPosePayloadDto payload; }
    [Serializable] public sealed class HeadRecenterCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public HeadRecenterPayloadDto payload; }
    [Serializable] public sealed class EmergencyStopCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public EmptyPayloadDto payload; }

    [Serializable]
    public sealed class PayloadDto
    {
        public string requested_mode;
        public string mode;
        public string frame;
        public QuaternionDto orientation;
        public PositionDto position;
    }

    [Serializable] public sealed class EmptyPayloadDto { }
    [Serializable] public sealed class SessionStartPayloadDto { public string requested_mode; }
    [Serializable] public sealed class ModeSetPayloadDto { public string mode; }
    [Serializable] public sealed class HeadRecenterPayloadDto { public string frame; public QuaternionDto orientation; }
    [Serializable] public sealed class HeadPosePayloadDto { public string frame; public QuaternionDto orientation; public PositionDto position; }

    [Serializable]
    public sealed class QuaternionDto
    {
        public double x;
        public double y;
        public double z;
        public double w;
    }

    [Serializable]
    public sealed class PositionDto
    {
        public double x;
        public double y;
        public double z;
    }

    [Serializable]
    public sealed class GatewayStateEventDto
    {
        public string schema_version;
        public string event_type;
        public long gateway_monotonic_ns;
        public string state;
        public Correlation correlation;
    }

    [Serializable]
    public sealed class NeckTargetEventDto
    {
        public string schema_version;
        public string event_type;
        public long gateway_monotonic_ns;
        public Correlation correlation;
        public double pan_degrees;
        public double tilt_degrees;
        public bool hold;
    }

    [Serializable]
    public sealed class SafetyStopEventDto
    {
        public string schema_version;
        public string event_type;
        public long gateway_monotonic_ns;
        public string reason;
        public Correlation correlation;
        public string neck_action;
        public string base_action;
        public string arm_action;
    }

    [Serializable]
    public sealed class CommandRejectedEventDto
    {
        public string schema_version;
        public string event_type;
        public long gateway_monotonic_ns;
        public string code;
        public string message;
        public Correlation correlation;
    }
}
