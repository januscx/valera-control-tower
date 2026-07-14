using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;
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
            RequireNonEmptyString(root, "session_id");
            RequireInteger(root, "sequence", 1);
            RequireInteger(root, "timestamp_ms", 0);
            JsonValue payload = RequireMember(root, "payload");
            RequireObject(payload, "payload");
            Type type = CommandType(command);
            ValidateCommandPayload(command, payload);
            object dto = JsonUtility.FromJson(json, type);
            if (dto == null) throw new WireValidationException("Command DTO deserialization failed.");
            return dto;
        }

        public static string EncodeCommand(object dto)
        {
            if (dto == null) throw new WireValidationException("Command DTO must not be null.");
            string json = JsonUtility.ToJson(dto);
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
            Type type;
            switch (eventType)
            {
                case WireValues.GatewayState:
                    RequireExactFields(root, Fields("schema_version", "event_type", "gateway_monotonic_ns", "state", "session_id", "sequence"));
                    RequireKnown(root, "state", "IDLE", "AWAITING_RECENTER", "HEAD_ACTIVE", "SAFE_STOPPED", "ESTOP_LATCHED"); type = typeof(GatewayStateEventDto); break;
                case WireValues.NeckTarget:
                    RequireExactFields(root, Fields("schema_version", "event_type", "gateway_monotonic_ns", "session_id", "sequence", "pan_degrees", "tilt_degrees", "hold"));
                    RequireNonEmptyString(root, "session_id"); RequireInteger(root, "sequence", 1); RequireFiniteNumber(root, "pan_degrees"); RequireFiniteNumber(root, "tilt_degrees"); RequireBoolean(root, "hold"); type = typeof(NeckTargetEventDto); break;
                case WireValues.SafetyStop:
                    RequireExactFields(root, Fields("schema_version", "event_type", "gateway_monotonic_ns", "reason", "session_id", "sequence", "neck_action", "base_action", "arm_action"));
                    RequireKnown(root, "reason", "WATCHDOG", "EMERGENCY_STOP", "SESSION_STOPPED"); RequireNonEmptyString(root, "neck_action"); RequireNonEmptyString(root, "base_action"); RequireNonEmptyString(root, "arm_action"); type = typeof(SafetyStopEventDto); break;
                case WireValues.CommandRejected:
                    RequireExactFields(root, Fields("schema_version", "event_type", "gateway_monotonic_ns", "code", "message", "session_id", "sequence"));
                    RequireKnown(root, "code", "STALE_SEQUENCE", "STALE_TIMESTAMP", "SESSION_MISMATCH", "NO_ACTIVE_SESSION", "MODE_BLOCKED", "UNKNOWN_MODE", "WATCHDOG_ACTIVE", "INVALID_PAYLOAD", "ESTOP_LATCHED"); RequireNonEmptyString(root, "message"); type = typeof(CommandRejectedEventDto); break;
                default: throw new WireValidationException("Unknown event type.");
            }
            ValidateNullableIdentifiers(root, eventType == WireValues.NeckTarget);
            object dto = JsonUtility.FromJson(json, type);
            if (dto == null) throw new WireValidationException("Event DTO deserialization failed.");
            return dto;
        }

        public static string EncodeEvent(object dto)
        {
            if (dto == null) throw new WireValidationException("Event DTO must not be null.");
            string json = JsonUtility.ToJson(dto);
            DecodeEvent(json);
            return json;
        }

        private static Type CommandType(string command)
        {
            switch (command)
            {
                case WireValues.SessionStart: return typeof(SessionStartCommandDto);
                case WireValues.SessionStop: return typeof(SessionStopCommandDto);
                case WireValues.ModeSet: return typeof(ModeSetCommandDto);
                case WireValues.HeadPose: return typeof(HeadPoseCommandDto);
                case WireValues.HeadRecenter: return typeof(HeadRecenterCommandDto);
                case WireValues.EmergencyStop: return typeof(EmergencyStopCommandDto);
                default: throw new WireValidationException("Unknown command.");
            }
        }

        private static void ValidateCommandPayload(string command, JsonValue payload)
        {
            if (command == WireValues.SessionStart) { RequireExactFields(payload, Fields("requested_mode")); RequireNonEmptyString(payload, "requested_mode"); return; }
            if (command == WireValues.ModeSet) { RequireExactFields(payload, Fields("mode")); RequireNonEmptyString(payload, "mode"); return; }
            if (command == WireValues.SessionStop || command == WireValues.EmergencyStop) { RequireExactFields(payload, Fields()); return; }
            bool positionAllowed = command == WireValues.HeadPose;
            RequireExactFields(payload, positionAllowed ? Fields("frame", "orientation", "position") : Fields("frame", "orientation"), positionAllowed ? Fields("position") : Fields());
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

        private static double Square(double value) { return value * value; }
        private static void RequireKnown(JsonValue value, string name, params string[] values) { string found = RequireString(value, name, null); foreach (string candidate in values) if (found == candidate) return; throw new WireValidationException(name + " has an unsupported value."); }
        private static void RequireBoolean(JsonValue value, string name) { if (RequireMember(value, name).kind != JsonKind.Boolean) throw new WireValidationException(name + " must be boolean."); }
        private static void ValidateNullableIdentifiers(JsonValue root, bool required)
        {
            JsonValue session = RequireMember(root, "session_id"); JsonValue sequence = RequireMember(root, "sequence");
            if (required || session.kind != JsonKind.Null) RequireNonEmptyString(root, "session_id");
            if (required || sequence.kind != JsonKind.Null) RequireInteger(root, "sequence", 1);
        }
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
        private static void RequireNonEmptyString(JsonValue objectValue, string name) { if (RequireString(objectValue, name, null).Length == 0) throw new WireValidationException(name + " must not be empty."); }
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
