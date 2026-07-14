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
    public sealed class CommandEnvelopeDto
    {
        public string schema_version;
        public string command;
        public string session_id;
        public long sequence;
        public long timestamp_ms;
        public PayloadDto payload;
    }

    [Serializable] public sealed class SessionStartCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public PayloadDto payload; }
    [Serializable] public sealed class SessionStopCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public PayloadDto payload; }
    [Serializable] public sealed class ModeSetCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public PayloadDto payload; }
    [Serializable] public sealed class HeadPoseCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public PayloadDto payload; }
    [Serializable] public sealed class HeadRecenterCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public PayloadDto payload; }
    [Serializable] public sealed class EmergencyStopCommandDto { public string schema_version; public string command; public string session_id; public long sequence; public long timestamp_ms; public PayloadDto payload; }

    [Serializable]
    public sealed class EventEnvelopeDto
    {
        public string schema_version;
        public string event_type;
        public long gateway_monotonic_ns;
        public string session_id;
        public long sequence;
    }

    [Serializable]
    public sealed class PayloadDto
    {
        public string requested_mode;
        public string mode;
        public string frame;
        public QuaternionDto orientation;
        public PositionDto position;
    }

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
        public string session_id;
        public long sequence;
    }

    [Serializable]
    public sealed class NeckTargetEventDto
    {
        public string schema_version;
        public string event_type;
        public long gateway_monotonic_ns;
        public string session_id;
        public long sequence;
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
        public string session_id;
        public long sequence;
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
        public string session_id;
        public long sequence;
    }
}
