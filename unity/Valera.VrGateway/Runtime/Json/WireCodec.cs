using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using Valera.VrGateway.Contracts;

namespace Valera.VrGateway.Json
{
    public static class WireCodec
    {
        private static readonly HashSet<string> CommandFields = Fields("schema_version", "command", "session_id", "sequence", "timestamp_ms", "payload");

        public static object DecodeCommand(string json)
        {
            JsonValue root = StrictJsonParser.Parse(json);
            RequireObject(root, "command root");
            RequireExactFields(root, CommandFields);
            RequireString(root, "schema_version", WireValues.SchemaVersion);
            string command = RequireString(root, "command", null);
            string sessionId = RequireNonEmptyString(root, "session_id");
            long sequence = RequireInteger(root, "sequence", 1);
            long timestampMs = RequireInteger(root, "timestamp_ms", 0);
            JsonValue payload = RequireMember(root, "payload");
            RequireObject(payload, "payload");
            ValidateCommandPayload(command, payload);
            switch (command)
            {
                case WireValues.SessionStart:
                    return new SessionStartCommandDto
                    {
                        schema_version = WireValues.SchemaVersion,
                        command = command,
                        session_id = sessionId,
                        sequence = sequence,
                        timestamp_ms = timestampMs,
                        payload = new SessionStartPayloadDto { requested_mode = RequireString(payload, "requested_mode", "head") },
                    };
                case WireValues.SessionStop:
                    return new SessionStopCommandDto
                    {
                        schema_version = WireValues.SchemaVersion,
                        command = command,
                        session_id = sessionId,
                        sequence = sequence,
                        timestamp_ms = timestampMs,
                        payload = new EmptyPayloadDto(),
                    };
                case WireValues.EmergencyStop:
                    return new EmergencyStopCommandDto
                    {
                        schema_version = WireValues.SchemaVersion,
                        command = command,
                        session_id = sessionId,
                        sequence = sequence,
                        timestamp_ms = timestampMs,
                        payload = new EmptyPayloadDto(),
                    };
                case WireValues.ModeSet:
                    return new ModeSetCommandDto
                    {
                        schema_version = WireValues.SchemaVersion,
                        command = command,
                        session_id = sessionId,
                        sequence = sequence,
                        timestamp_ms = timestampMs,
                        payload = new ModeSetPayloadDto { mode = RequireString(payload, "mode", null) },
                    };
                case WireValues.HeadPose:
                    return new HeadPoseCommandDto
                    {
                        schema_version = WireValues.SchemaVersion,
                        command = command,
                        session_id = sessionId,
                        sequence = sequence,
                        timestamp_ms = timestampMs,
                        payload = DecodePosePayload(payload, allowPosition: true),
                    };
                case WireValues.HeadRecenter:
                    return new HeadRecenterCommandDto
                    {
                        schema_version = WireValues.SchemaVersion,
                        command = command,
                        session_id = sessionId,
                        sequence = sequence,
                        timestamp_ms = timestampMs,
                        payload = DecodeHeadRecenterPayload(payload),
                    };
                default:
                    throw new WireValidationException("Unknown command.");
            }
        }

        public static string EncodeCommand(object dto)
        {
            if (dto == null) throw new WireValidationException("Command DTO must not be null.");
            string json;
            switch (dto)
            {
                case SessionStartCommandDto c: json = EncodeSessionStart(c); break;
                case SessionStopCommandDto c: json = EncodeSessionStop(c); break;
                case ModeSetCommandDto c: json = EncodeModeSet(c); break;
                case HeadPoseCommandDto c: json = EncodeHeadPose(c); break;
                case HeadRecenterCommandDto c: json = EncodeHeadRecenter(c); break;
                case EmergencyStopCommandDto c: json = EncodeEmergencyStop(c); break;
                default: throw new WireValidationException("Unsupported command DTO type.");
            }
            DecodeCommand(json);
            return json;
        }

        public static object DecodeEvent(string json)
        {
            JsonValue root = StrictJsonParser.Parse(json);
            RequireObject(root, "event root");
            RequireString(root, "schema_version", WireValues.SchemaVersion);
            string eventType = RequireString(root, "event_type", null);
            RequireInteger(root, "gateway_monotonic_ns", 0);
            switch (eventType)
            {
                case WireValues.GatewayState:
                    RequireExactFields(root, Fields("schema_version", "event_type", "gateway_monotonic_ns", "state", "session_id", "sequence"));
                    RequireKnown(root, "state", "IDLE", "AWAITING_RECENTER", "HEAD_ACTIVE", "SAFE_STOPPED", "ESTOP_LATCHED");
                    return DecodeGatewayState(root);
                case WireValues.NeckTarget:
                    RequireExactFields(root, Fields("schema_version", "event_type", "gateway_monotonic_ns", "session_id", "sequence", "pan_degrees", "tilt_degrees", "hold"));
                    RequireFiniteNumber(root, "pan_degrees"); RequireFiniteNumber(root, "tilt_degrees"); RequireBoolean(root, "hold");
                    return DecodeNeckTarget(root, requireCorrelation: true);
                case WireValues.SafetyStop:
                    RequireExactFields(root, Fields("schema_version", "event_type", "gateway_monotonic_ns", "reason", "session_id", "sequence", "neck_action", "base_action", "arm_action"));
                    RequireKnown(root, "reason", "WATCHDOG", "EMERGENCY_STOP", "SESSION_STOPPED"); RequireNonEmptyString(root, "neck_action"); RequireNonEmptyString(root, "base_action"); RequireNonEmptyString(root, "arm_action");
                    return DecodeSafetyStop(root);
                case WireValues.CommandRejected:
                    RequireExactFields(root, Fields("schema_version", "event_type", "gateway_monotonic_ns", "code", "message", "session_id", "sequence"));
                    RequireKnown(root, "code", "STALE_SEQUENCE", "STALE_TIMESTAMP", "SESSION_MISMATCH", "NO_ACTIVE_SESSION", "MODE_BLOCKED", "UNKNOWN_MODE", "WATCHDOG_ACTIVE", "INVALID_PAYLOAD", "ESTOP_LATCHED"); RequireNonEmptyString(root, "message");
                    return DecodeCommandRejected(root);
                default: throw new WireValidationException("Unknown event type.");
            }
        }

        public static string EncodeEvent(object dto)
        {
            if (dto == null) throw new WireValidationException("Event DTO must not be null.");
            string json;
            switch (dto)
            {
                case GatewayStateEventDto e: json = EncodeGatewayState(e); break;
                case NeckTargetEventDto e: json = EncodeNeckTarget(e); break;
                case SafetyStopEventDto e: json = EncodeSafetyStop(e); break;
                case CommandRejectedEventDto e: json = EncodeCommandRejected(e); break;
                default: throw new WireValidationException("Unsupported event DTO type.");
            }
            DecodeEvent(json);
            return json;
        }

        private static HeadPosePayloadDto DecodePosePayload(JsonValue payload, bool allowPosition)
        {
            RequireString(payload, "frame", "quest_local");
            JsonValue orientation = RequireMember(payload, "orientation");
            RequireExactFields(orientation, Fields("x", "y", "z", "w"));
            QuaternionDto quaternion = new QuaternionDto
            {
                x = RequireFiniteNumber(orientation, "x"),
                y = RequireFiniteNumber(orientation, "y"),
                z = RequireFiniteNumber(orientation, "z"),
                w = RequireFiniteNumber(orientation, "w"),
            };
            double squared = Square(quaternion.x) + Square(quaternion.y) + Square(quaternion.z) + Square(quaternion.w);
            if (!double.IsFinite(squared) || squared <= 1e-24) throw new WireValidationException("Quaternion must be finite and non-zero.");

            PositionDto position = null;
            if (allowPosition && payload.members.ContainsKey("position"))
            {
                JsonValue positionValue = payload.members["position"];
                if (positionValue.kind != JsonKind.Null)
                {
                    RequireObject(positionValue, "position");
                    RequireExactFields(positionValue, Fields("x", "y", "z"));
                    position = new PositionDto
                    {
                        x = RequireFiniteNumber(positionValue, "x"),
                        y = RequireFiniteNumber(positionValue, "y"),
                        z = RequireFiniteNumber(positionValue, "z"),
                    };
                }
            }

            return new HeadPosePayloadDto { frame = "quest_local", orientation = quaternion, position = position };
        }

        private static HeadRecenterPayloadDto DecodeHeadRecenterPayload(JsonValue payload)
        {
            HeadPosePayloadDto pose = DecodePosePayload(payload, allowPosition: false);
            return new HeadRecenterPayloadDto { frame = pose.frame, orientation = pose.orientation };
        }

        private static void ValidateCommandPayload(string command, JsonValue payload)
        {
            if (command == WireValues.SessionStart) { RequireExactFields(payload, Fields("requested_mode")); RequireString(payload, "requested_mode", "head"); return; }
            if (command == WireValues.ModeSet) { RequireExactFields(payload, Fields("mode")); RequireModeStringFromJson(payload); return; }
            if (command == WireValues.SessionStop || command == WireValues.EmergencyStop) { RequireExactFields(payload, Fields()); return; }
            bool positionAllowed = command == WireValues.HeadPose;
            RequireExactFields(payload, Fields("frame", "orientation"), positionAllowed ? Fields("position") : Fields());
            RequireString(payload, "frame", "quest_local");
            JsonValue orientation = RequireMember(payload, "orientation");
            RequireExactFields(orientation, Fields("x", "y", "z", "w"));
            double squared = RequireFiniteNumber(orientation, "x");
            squared = squared * squared + Square(RequireFiniteNumber(orientation, "y")) + Square(RequireFiniteNumber(orientation, "z")) + Square(RequireFiniteNumber(orientation, "w"));
            if (!double.IsFinite(squared) || squared <= 1e-24) throw new WireValidationException("Quaternion must be finite and non-zero.");
            if (positionAllowed && payload.members.ContainsKey("position") && payload.members["position"].kind != JsonKind.Null)
            {
                JsonValue position = payload.members["position"];
                RequireExactFields(position, Fields("x", "y", "z"));
                RequireFiniteNumber(position, "x"); RequireFiniteNumber(position, "y"); RequireFiniteNumber(position, "z");
            }
        }

        private static GatewayStateEventDto DecodeGatewayState(JsonValue root)
        {
            return new GatewayStateEventDto
            {
                schema_version = WireValues.SchemaVersion,
                event_type = WireValues.GatewayState,
                gateway_monotonic_ns = RequireInteger(root, "gateway_monotonic_ns", 0),
                state = RequireString(root, "state", null),
                correlation = DecodeCorrelation(root, required: false),
            };
        }

        private static NeckTargetEventDto DecodeNeckTarget(JsonValue root, bool requireCorrelation)
        {
            return new NeckTargetEventDto
            {
                schema_version = WireValues.SchemaVersion,
                event_type = WireValues.NeckTarget,
                gateway_monotonic_ns = RequireInteger(root, "gateway_monotonic_ns", 0),
                correlation = DecodeCorrelation(root, required: requireCorrelation),
                pan_degrees = RequireFiniteNumber(root, "pan_degrees"),
                tilt_degrees = RequireFiniteNumber(root, "tilt_degrees"),
                hold = RequireMember(root, "hold").kind == JsonKind.Boolean && RequireMember(root, "hold").boolean,
            };
        }

        private static SafetyStopEventDto DecodeSafetyStop(JsonValue root)
        {
            return new SafetyStopEventDto
            {
                schema_version = WireValues.SchemaVersion,
                event_type = WireValues.SafetyStop,
                gateway_monotonic_ns = RequireInteger(root, "gateway_monotonic_ns", 0),
                reason = RequireString(root, "reason", null),
                correlation = DecodeCorrelation(root, required: false),
                neck_action = RequireString(root, "neck_action", null),
                base_action = RequireString(root, "base_action", null),
                arm_action = RequireString(root, "arm_action", null),
            };
        }

        private static CommandRejectedEventDto DecodeCommandRejected(JsonValue root)
        {
            return new CommandRejectedEventDto
            {
                schema_version = WireValues.SchemaVersion,
                event_type = WireValues.CommandRejected,
                gateway_monotonic_ns = RequireInteger(root, "gateway_monotonic_ns", 0),
                code = RequireString(root, "code", null),
                message = RequireString(root, "message", null),
                correlation = DecodeCorrelation(root, required: false),
            };
        }

        private static Correlation DecodeCorrelation(JsonValue root, bool required)
        {
            JsonValue session = RequireMember(root, "session_id");
            JsonValue sequence = RequireMember(root, "sequence");
            bool sessionNull = session.kind == JsonKind.Null;
            bool sequenceNull = sequence.kind == JsonKind.Null;

            if (sessionNull && sequenceNull)
            {
                if (required) throw new WireValidationException("session_id and sequence are required for this event type.");
                return Correlation.Unavailable;
            }

            if (sessionNull || sequenceNull) throw new WireValidationException("Partial correlation is not allowed.");
            string sessionId = RequireNonEmptyString(root, "session_id");
            long sequenceValue = RequireInteger(root, "sequence", 1);
            return new Correlation(sessionId, sequenceValue);
        }

        private static string EncodeGatewayState(GatewayStateEventDto dto)
        {
            ValidateEventHeader(dto.schema_version, dto.event_type, WireValues.GatewayState);
            RequireKnownValue(dto.state, "state", "IDLE", "AWAITING_RECENTER", "HEAD_ACTIVE", "SAFE_STOPPED", "ESTOP_LATCHED");
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "event_type", dto.event_type); builder.Append(',');
            AppendNumber(builder, "gateway_monotonic_ns", dto.gateway_monotonic_ns); builder.Append(',');
            AppendString(builder, "state", dto.state); builder.Append(',');
            AppendCorrelation(builder, dto.correlation); builder.Append('}');
            return builder.ToString();
        }

        private static string EncodeNeckTarget(NeckTargetEventDto dto)
        {
            ValidateEventHeader(dto.schema_version, dto.event_type, WireValues.NeckTarget);
            if (!dto.correlation.IsAvailable) throw new WireValidationException("neck.target requires correlation.");
            ValidateFinite(dto.pan_degrees, "pan_degrees"); ValidateFinite(dto.tilt_degrees, "tilt_degrees");
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "event_type", dto.event_type); builder.Append(',');
            AppendNumber(builder, "gateway_monotonic_ns", dto.gateway_monotonic_ns); builder.Append(',');
            AppendCorrelation(builder, dto.correlation); builder.Append(',');
            AppendNumber(builder, "pan_degrees", dto.pan_degrees); builder.Append(',');
            AppendNumber(builder, "tilt_degrees", dto.tilt_degrees); builder.Append(',');
            AppendBoolean(builder, "hold", dto.hold); builder.Append('}');
            return builder.ToString();
        }

        private static string EncodeSafetyStop(SafetyStopEventDto dto)
        {
            ValidateEventHeader(dto.schema_version, dto.event_type, WireValues.SafetyStop);
            RequireKnownValue(dto.reason, "reason", "WATCHDOG", "EMERGENCY_STOP", "SESSION_STOPPED");
            RequireNonEmpty(dto.neck_action, "neck_action"); RequireNonEmpty(dto.base_action, "base_action"); RequireNonEmpty(dto.arm_action, "arm_action");
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "event_type", dto.event_type); builder.Append(',');
            AppendNumber(builder, "gateway_monotonic_ns", dto.gateway_monotonic_ns); builder.Append(',');
            AppendString(builder, "reason", dto.reason); builder.Append(',');
            AppendCorrelation(builder, dto.correlation); builder.Append(',');
            AppendString(builder, "neck_action", dto.neck_action); builder.Append(',');
            AppendString(builder, "base_action", dto.base_action); builder.Append(',');
            AppendString(builder, "arm_action", dto.arm_action); builder.Append('}');
            return builder.ToString();
        }

        private static string EncodeCommandRejected(CommandRejectedEventDto dto)
        {
            ValidateEventHeader(dto.schema_version, dto.event_type, WireValues.CommandRejected);
            RequireKnownValue(dto.code, "code", "STALE_SEQUENCE", "STALE_TIMESTAMP", "SESSION_MISMATCH", "NO_ACTIVE_SESSION", "MODE_BLOCKED", "UNKNOWN_MODE", "WATCHDOG_ACTIVE", "INVALID_PAYLOAD", "ESTOP_LATCHED");
            RequireNonEmpty(dto.message, "message");
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "event_type", dto.event_type); builder.Append(',');
            AppendNumber(builder, "gateway_monotonic_ns", dto.gateway_monotonic_ns); builder.Append(',');
            AppendString(builder, "code", dto.code); builder.Append(',');
            AppendString(builder, "message", dto.message); builder.Append(',');
            AppendCorrelation(builder, dto.correlation); builder.Append('}');
            return builder.ToString();
        }

        private static string EncodeSessionStart(SessionStartCommandDto dto)
        {
            ValidateCommandHeader(dto.schema_version, dto.command, WireValues.SessionStart);
            RequireNonEmpty(dto.session_id, "session_id"); RequireSequence(dto.sequence); RequireTimestamp(dto.timestamp_ms);
            RequireStringExact(dto.payload.requested_mode, "requested_mode", "head");
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "command", dto.command); builder.Append(',');
            AppendString(builder, "session_id", dto.session_id); builder.Append(',');
            AppendNumber(builder, "sequence", dto.sequence); builder.Append(',');
            AppendNumber(builder, "timestamp_ms", dto.timestamp_ms); builder.Append(',');
            builder.Append('"'); builder.Append("payload"); builder.Append("\":{");
            AppendString(builder, "requested_mode", dto.payload.requested_mode);
            builder.Append("}}");
            return builder.ToString();
        }

        private static string EncodeSessionStop(SessionStopCommandDto dto)
        {
            ValidateCommandHeader(dto.schema_version, dto.command, WireValues.SessionStop);
            RequireNonEmpty(dto.session_id, "session_id"); RequireSequence(dto.sequence); RequireTimestamp(dto.timestamp_ms);
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "command", dto.command); builder.Append(',');
            AppendString(builder, "session_id", dto.session_id); builder.Append(',');
            AppendNumber(builder, "sequence", dto.sequence); builder.Append(',');
            AppendNumber(builder, "timestamp_ms", dto.timestamp_ms); builder.Append(',');
            builder.Append('"'); builder.Append("payload"); builder.Append("\":{}");
            builder.Append('}');
            return builder.ToString();
        }

        private static string EncodeModeSet(ModeSetCommandDto dto)
        {
            ValidateCommandHeader(dto.schema_version, dto.command, WireValues.ModeSet);
            RequireNonEmpty(dto.session_id, "session_id"); RequireSequence(dto.sequence); RequireTimestamp(dto.timestamp_ms);
            RequireModeString(dto.payload.mode);
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "command", dto.command); builder.Append(',');
            AppendString(builder, "session_id", dto.session_id); builder.Append(',');
            AppendNumber(builder, "sequence", dto.sequence); builder.Append(',');
            AppendNumber(builder, "timestamp_ms", dto.timestamp_ms); builder.Append(',');
            builder.Append('"'); builder.Append("payload"); builder.Append("\":{");
            AppendString(builder, "mode", dto.payload.mode);
            builder.Append("}}");
            return builder.ToString();
        }

        private static string EncodeHeadPose(HeadPoseCommandDto dto)
        {
            ValidateCommandHeader(dto.schema_version, dto.command, WireValues.HeadPose);
            RequireNonEmpty(dto.session_id, "session_id"); RequireSequence(dto.sequence); RequireTimestamp(dto.timestamp_ms);
            RequireStringExact(dto.payload.frame, "frame", "quest_local");
            QuaternionDto q = dto.payload.orientation;
            ValidateQuaternion(q);
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "command", dto.command); builder.Append(',');
            AppendString(builder, "session_id", dto.session_id); builder.Append(',');
            AppendNumber(builder, "sequence", dto.sequence); builder.Append(',');
            AppendNumber(builder, "timestamp_ms", dto.timestamp_ms); builder.Append(',');
            builder.Append('"'); builder.Append("payload"); builder.Append("\":{");
            AppendString(builder, "frame", dto.payload.frame); builder.Append(',');
            AppendQuaternion(builder, q);
            if (dto.payload.position != null)
            {
                builder.Append(',');
                AppendPosition(builder, dto.payload.position);
            }
            builder.Append("}}");
            return builder.ToString();
        }

        private static string EncodeHeadRecenter(HeadRecenterCommandDto dto)
        {
            ValidateCommandHeader(dto.schema_version, dto.command, WireValues.HeadRecenter);
            RequireNonEmpty(dto.session_id, "session_id"); RequireSequence(dto.sequence); RequireTimestamp(dto.timestamp_ms);
            RequireStringExact(dto.payload.frame, "frame", "quest_local");
            ValidateQuaternion(dto.payload.orientation);
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "command", dto.command); builder.Append(',');
            AppendString(builder, "session_id", dto.session_id); builder.Append(',');
            AppendNumber(builder, "sequence", dto.sequence); builder.Append(',');
            AppendNumber(builder, "timestamp_ms", dto.timestamp_ms); builder.Append(',');
            builder.Append('"'); builder.Append("payload"); builder.Append("\":{");
            AppendString(builder, "frame", dto.payload.frame); builder.Append(',');
            AppendQuaternion(builder, dto.payload.orientation);
            builder.Append("}}");
            return builder.ToString();
        }

        private static string EncodeEmergencyStop(EmergencyStopCommandDto dto)
        {
            ValidateCommandHeader(dto.schema_version, dto.command, WireValues.EmergencyStop);
            RequireNonEmpty(dto.session_id, "session_id"); RequireSequence(dto.sequence); RequireTimestamp(dto.timestamp_ms);
            var builder = new StringBuilder();
            builder.Append('{');
            AppendString(builder, "schema_version", dto.schema_version); builder.Append(',');
            AppendString(builder, "command", dto.command); builder.Append(',');
            AppendString(builder, "session_id", dto.session_id); builder.Append(',');
            AppendNumber(builder, "sequence", dto.sequence); builder.Append(',');
            AppendNumber(builder, "timestamp_ms", dto.timestamp_ms); builder.Append(',');
            builder.Append('"'); builder.Append("payload"); builder.Append("\":{}");
            builder.Append('}');
            return builder.ToString();
        }

        private static void ValidateCommandHeader(string schemaVersion, string command, string expectedCommand)
        {
            if (schemaVersion != WireValues.SchemaVersion) throw new WireValidationException("schema_version must be 0.1.");
            if (command != expectedCommand) throw new WireValidationException("command mismatch.");
        }

        private static void ValidateEventHeader(string schemaVersion, string eventType, string expectedEventType)
        {
            if (schemaVersion != WireValues.SchemaVersion) throw new WireValidationException("schema_version must be 0.1.");
            if (eventType != expectedEventType) throw new WireValidationException("event_type mismatch.");
        }

        private static void AppendString(StringBuilder builder, string name, string value)
        {
            builder.Append('"'); builder.Append(name); builder.Append("\":");
            if (value == null) { builder.Append("null"); return; }
            builder.Append('"');
            foreach (char c in value)
            {
                switch (c)
                {
                    case '"': builder.Append("\\\""); break;
                    case '\\': builder.Append("\\\\"); break;
                    case '\b': builder.Append("\\b"); break;
                    case '\f': builder.Append("\\f"); break;
                    case '\n': builder.Append("\\n"); break;
                    case '\r': builder.Append("\\r"); break;
                    case '\t': builder.Append("\\t"); break;
                    default:
                        if (c < 0x20) builder.AppendFormat("\\u{0:X4}", (int)c);
                        else builder.Append(c);
                        break;
                }
            }
            builder.Append('"');
        }

        private static void AppendNumber(StringBuilder builder, string name, long value)
        {
            builder.Append('"'); builder.Append(name); builder.Append("\":");
            builder.Append(value.ToString(CultureInfo.InvariantCulture));
        }

        private static void AppendNumber(StringBuilder builder, string name, double value)
        {
            builder.Append('"'); builder.Append(name); builder.Append("\":");
            if (!double.IsFinite(value)) throw new WireValidationException(name + " must be finite.");
            builder.Append(value.ToString(CultureInfo.InvariantCulture));
        }

        private static void AppendBoolean(StringBuilder builder, string name, bool value)
        {
            builder.Append('"'); builder.Append(name); builder.Append("\":");
            builder.Append(value ? "true" : "false");
        }

        private static void AppendCorrelation(StringBuilder builder, Correlation correlation)
        {
            AppendString(builder, "session_id", correlation.IsAvailable ? correlation.SessionId : null);
            builder.Append(',');
            AppendNullableNumber(builder, "sequence", correlation.IsAvailable ? correlation.Sequence : (long?)null);
        }

        private static void AppendNullableNumber(StringBuilder builder, string name, long? value)
        {
            builder.Append('"'); builder.Append(name); builder.Append("\":");
            if (value.HasValue) builder.Append(value.Value.ToString(CultureInfo.InvariantCulture));
            else builder.Append("null");
        }

        private static void ValidateFinite(double value, string name) { if (!double.IsFinite(value)) throw new WireValidationException(name + " must be finite."); }
        private static void RequireNonEmpty(string value, string name) { if (string.IsNullOrEmpty(value) || string.IsNullOrWhiteSpace(value)) throw new WireValidationException(name + " must not be empty or whitespace."); }
        private static void RequireKnownValue(string value, string name, params string[] values) { foreach (string candidate in values) if (value == candidate) return; throw new WireValidationException(name + " has an unsupported value."); }
        private static void RequireStringExact(string value, string name, string expected) { if (value != expected) throw new WireValidationException(name + " has an unsupported value."); }
        private static void RequireSequence(long value) { if (value < 1) throw new WireValidationException("sequence must be at least 1."); }
        private static void RequireTimestamp(long value) { if (value < 0) throw new WireValidationException("timestamp_ms must be non-negative."); }
        private static void RequireModeString(string mode)
        {
            if (string.IsNullOrEmpty(mode) || mode.Length > 64 || string.IsNullOrWhiteSpace(mode)) throw new WireValidationException("mode must be a bounded non-whitespace string.");
        }
        private static void ValidateQuaternion(QuaternionDto q)
        {
            double squared = Square(q.x) + Square(q.y) + Square(q.z) + Square(q.w);
            if (!double.IsFinite(squared) || squared <= 1e-24) throw new WireValidationException("Quaternion must be finite and non-zero.");
        }
        private static void AppendQuaternion(StringBuilder builder, QuaternionDto q)
        {
            builder.Append('"'); builder.Append("orientation"); builder.Append("\":{");
            AppendNumber(builder, "x", q.x); builder.Append(',');
            AppendNumber(builder, "y", q.y); builder.Append(',');
            AppendNumber(builder, "z", q.z); builder.Append(',');
            AppendNumber(builder, "w", q.w);
            builder.Append('}');
        }
        private static void AppendPosition(StringBuilder builder, PositionDto p)
        {
            builder.Append('"'); builder.Append("position"); builder.Append("\":{");
            AppendNumber(builder, "x", p.x); builder.Append(',');
            AppendNumber(builder, "y", p.y); builder.Append(',');
            AppendNumber(builder, "z", p.z);
            builder.Append('}');
        }
        private static double Square(double value) { return value * value; }
        private static void RequireKnown(JsonValue value, string name, params string[] values) { string found = RequireString(value, name, null); foreach (string candidate in values) if (found == candidate) return; throw new WireValidationException(name + " has an unsupported value."); }
        private static void RequireBoolean(JsonValue value, string name) { if (RequireMember(value, name).kind != JsonKind.Boolean) throw new WireValidationException(name + " must be boolean."); }
        private static HashSet<string> Fields(params string[] values) { return new HashSet<string>(values, StringComparer.Ordinal); }
        private static JsonValue RequireMember(JsonValue objectValue, string name) { JsonValue value; if (!objectValue.members.TryGetValue(name, out value)) throw new WireValidationException("Missing field: " + name); return value; }
        private static void RequireObject(JsonValue value, string context) { if (value == null || value.kind != JsonKind.Object) throw new WireValidationException(context + " must be an object."); }
        private static void RequireExactFields(JsonValue value, HashSet<string> required, HashSet<string> optional = null)
        {
            RequireObject(value, "JSON value");
            foreach (string name in required) if (!value.members.ContainsKey(name)) throw new WireValidationException("Missing field: " + name);
            foreach (string name in value.members.Keys) if (!required.Contains(name) && (optional == null || !optional.Contains(name))) throw new WireValidationException("Unexpected field: " + name);
        }
        private static string RequireString(JsonValue objectValue, string name, string expected)
        {
            JsonValue value = RequireMember(objectValue, name);
            if (value.kind != JsonKind.String) throw new WireValidationException(name + " must be a string.");
            if (expected != null && value.text != expected) throw new WireValidationException(name + " has an unsupported value.");
            return value.text;
        }
        private static string RequireNonEmptyString(JsonValue objectValue, string name) { string text = RequireString(objectValue, name, null); if (text.Length == 0 || string.IsNullOrWhiteSpace(text)) throw new WireValidationException(name + " must not be empty or whitespace."); return text; }
        private static void RequireModeStringFromJson(JsonValue objectValue)
        {
            string mode = RequireString(objectValue, "mode", null);
            if (mode.Length == 0 || mode.Length > 64 || string.IsNullOrWhiteSpace(mode)) throw new WireValidationException("mode must be a bounded non-whitespace string.");
        }
        private static long RequireInteger(JsonValue objectValue, string name, long minimum)
        {
            JsonValue value = RequireMember(objectValue, name);
            if (value.kind != JsonKind.Number || value.text.IndexOfAny(new[] { '.', 'e', 'E' }) >= 0 || !long.TryParse(value.text, NumberStyles.None, CultureInfo.InvariantCulture, out long parsed) || parsed < minimum) throw new WireValidationException(name + " must be an in-range integer.");
            return parsed;
        }
        private static double RequireFiniteNumber(JsonValue objectValue, string name)
        {
            JsonValue value = RequireMember(objectValue, name);
            if (value.kind != JsonKind.Number || !double.TryParse(value.text, NumberStyles.Float, CultureInfo.InvariantCulture, out double parsed) || !double.IsFinite(parsed)) throw new WireValidationException(name + " must be finite.");
            return parsed;
        }
    }
}
