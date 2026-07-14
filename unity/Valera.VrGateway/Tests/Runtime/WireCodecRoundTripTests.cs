using System.Reflection;
using NUnit.Framework;
using Valera.VrGateway.Contracts;

namespace Valera.VrGateway.Tests
{
    public sealed class WireCodecRoundTripTests
    {
        [Test]
        public void Codec_RoundTripsSessionStartAndNeckTarget()
        {
            var command = new SessionStartCommandDto { schema_version = "0.1", command = "session.start", session_id = "session-1", sequence = 1, timestamp_ms = 0, payload = new SessionStartPayloadDto { requested_mode = "head" } };
            var target = new NeckTargetEventDto { schema_version = "0.1", event_type = "neck.target", gateway_monotonic_ns = 1, correlation = new Correlation("session-1", 2), pan_degrees = 1.0, tilt_degrees = -2.0, hold = false };

            Assert.That(DecodeCommand(Encode("EncodeCommand", command)).GetType(), Is.EqualTo(typeof(SessionStartCommandDto)));
            Assert.That(DecodeEvent(Encode("EncodeEvent", target)).GetType(), Is.EqualTo(typeof(NeckTargetEventDto)));
        }

        [Test]
        public void Codec_PreservesUnknownNonEmptyMode()
        {
            var command = new ModeSetCommandDto { schema_version = "0.1", command = "mode.set", session_id = "session-1", sequence = 2, timestamp_ms = 1, payload = new ModeSetPayloadDto { mode = "inspection" } };
            string json = Encode("EncodeCommand", command);

            Assert.That(json, Does.Contain("\"mode\":\"inspection\""));
            var decoded = (ModeSetCommandDto)DecodeCommand(json);
            Assert.That(decoded.payload.mode, Is.EqualTo("inspection"));
        }

        [TestCaseSource(nameof(CommandRoundTripCases))]
        public void Codec_RoundTripsCommand(object command)
        {
            string json = Encode("EncodeCommand", command);
            object decoded = DecodeCommand(json);
            Assert.That(decoded.GetType(), Is.EqualTo(command.GetType()));
            AssertCommandEquality(command, decoded);
        }

        [TestCaseSource(nameof(EventRoundTripCases))]
        public void Codec_RoundTripsEvent(object evt)
        {
            string json = Encode("EncodeEvent", evt);
            object decoded = DecodeEvent(json);
            Assert.That(decoded.GetType(), Is.EqualTo(evt.GetType()));
            AssertEventEquality(evt, decoded);
        }

        private static object[] CommandRoundTripCases()
        {
            return new object[]
            {
                new SessionStartCommandDto { schema_version = "0.1", command = "session.start", session_id = "s-1", sequence = 1, timestamp_ms = 0, payload = new SessionStartPayloadDto { requested_mode = "head" } },
                new SessionStopCommandDto { schema_version = "0.1", command = "session.stop", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new EmptyPayloadDto() },
                new ModeSetCommandDto { schema_version = "0.1", command = "mode.set", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new ModeSetPayloadDto { mode = "head" } },
                new ModeSetCommandDto { schema_version = "0.1", command = "mode.set", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new ModeSetPayloadDto { mode = "drive" } },
                new ModeSetCommandDto { schema_version = "0.1", command = "mode.set", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new ModeSetPayloadDto { mode = "arm" } },
                new ModeSetCommandDto { schema_version = "0.1", command = "mode.set", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new ModeSetPayloadDto { mode = "inspection" } },
                new HeadPoseCommandDto { schema_version = "0.1", command = "head.pose", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new HeadPosePayloadDto { frame = "quest_local", orientation = new QuaternionDto { x = 0, y = 0, z = 0, w = 1 }, position = new PositionDto { x = 1, y = 2, z = 3 } } },
                new HeadPoseCommandDto { schema_version = "0.1", command = "head.pose", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new HeadPosePayloadDto { frame = "quest_local", orientation = new QuaternionDto { x = 0, y = 0, z = 0, w = 1 } } },
                new HeadRecenterCommandDto { schema_version = "0.1", command = "head.recenter", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new HeadRecenterPayloadDto { frame = "quest_local", orientation = new QuaternionDto { x = 0, y = 0, z = 0, w = 1 } } },
                new EmergencyStopCommandDto { schema_version = "0.1", command = "emergency_stop", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new EmptyPayloadDto() },
            };
        }

        private static object[] EventRoundTripCases()
        {
            var cases = new System.Collections.Generic.List<object>
            {
                new GatewayStateEventDto { schema_version = "0.1", event_type = "gateway.state", gateway_monotonic_ns = 1, state = "IDLE", correlation = Correlation.Unavailable },
                new GatewayStateEventDto { schema_version = "0.1", event_type = "gateway.state", gateway_monotonic_ns = 1, state = "AWAITING_RECENTER", correlation = new Correlation("s-1", 1) },
                new GatewayStateEventDto { schema_version = "0.1", event_type = "gateway.state", gateway_monotonic_ns = 1, state = "HEAD_ACTIVE", correlation = new Correlation("s-1", 2) },
                new GatewayStateEventDto { schema_version = "0.1", event_type = "gateway.state", gateway_monotonic_ns = 1, state = "SAFE_STOPPED", correlation = Correlation.Unavailable },
                new GatewayStateEventDto { schema_version = "0.1", event_type = "gateway.state", gateway_monotonic_ns = 1, state = "ESTOP_LATCHED", correlation = new Correlation("s-1", 99) },
                new NeckTargetEventDto { schema_version = "0.1", event_type = "neck.target", gateway_monotonic_ns = 1, correlation = new Correlation("s-1", 2), pan_degrees = 1.0, tilt_degrees = -2.0, hold = false },
                new NeckTargetEventDto { schema_version = "0.1", event_type = "neck.target", gateway_monotonic_ns = 1, correlation = new Correlation("s-1", 3), pan_degrees = -15.5, tilt_degrees = 10.0, hold = true },
                new SafetyStopEventDto { schema_version = "0.1", event_type = "safety.stop", gateway_monotonic_ns = 1, reason = "WATCHDOG", correlation = Correlation.Unavailable, neck_action = "HOLD_LAST_POSITION", base_action = "STOP", arm_action = "HOLD" },
                new SafetyStopEventDto { schema_version = "0.1", event_type = "safety.stop", gateway_monotonic_ns = 1, reason = "EMERGENCY_STOP", correlation = new Correlation("s-1", 5), neck_action = "HOLD_LAST_POSITION", base_action = "STOP", arm_action = "HOLD" },
                new SafetyStopEventDto { schema_version = "0.1", event_type = "safety.stop", gateway_monotonic_ns = 1, reason = "SESSION_STOPPED", correlation = new Correlation("s-1", 7), neck_action = "CENTER", base_action = "STOP", arm_action = "HOME" },
            };

            string[] rejectionCodes = {
                "STALE_SEQUENCE", "STALE_TIMESTAMP", "SESSION_MISMATCH", "NO_ACTIVE_SESSION",
                "MODE_BLOCKED", "UNKNOWN_MODE", "WATCHDOG_ACTIVE", "INVALID_PAYLOAD", "ESTOP_LATCHED"
            };
            string[] rejectionMessages = {
                "Sequence must increase within the session.",
                "Timestamp must not decrease within the session.",
                "Command does not match the active session.",
                "No active session is available.",
                "Requested operation is blocked in this mode.",
                "Requested mode is not recognized.",
                "The motion watchdog is active.",
                "Command payload is invalid.",
                "Emergency stop is latched.",
            };
            for (int i = 0; i < rejectionCodes.Length; i++)
            {
                cases.Add(new CommandRejectedEventDto
                {
                    schema_version = "0.1",
                    event_type = "command.rejected",
                    gateway_monotonic_ns = 1,
                    code = rejectionCodes[i],
                    message = rejectionMessages[i],
                    correlation = i % 2 == 0 ? Correlation.Unavailable : new Correlation("s-1", i + 1),
                });
            }

            return cases.ToArray();
        }

        private static void AssertCommandEquality(object expected, object actual)
        {
            foreach (FieldInfo field in expected.GetType().GetFields())
            {
                object expectedValue = field.GetValue(expected);
                object actualValue = field.GetValue(actual);
                if (field.FieldType == typeof(PayloadDto) || field.FieldType.IsClass && field.FieldType != typeof(string))
                {
                    if (expectedValue != null && actualValue != null) AssertPayloadEquality(expectedValue, actualValue);
                    else Assert.That(actualValue, Is.EqualTo(expectedValue), field.Name);
                }
                else
                {
                    Assert.That(actualValue, Is.EqualTo(expectedValue), field.Name);
                }
            }
        }

        private static void AssertPayloadEquality(object expected, object actual)
        {
            foreach (FieldInfo field in expected.GetType().GetFields())
            {
                object expectedValue = field.GetValue(expected);
                object actualValue = field.GetValue(actual);
                if (field.FieldType == typeof(QuaternionDto) || field.FieldType == typeof(PositionDto))
                {
                    if (expectedValue != null && actualValue != null) AssertPayloadEquality(expectedValue, actualValue);
                    else Assert.That(actualValue, Is.EqualTo(expectedValue), field.Name);
                }
                else
                {
                    Assert.That(actualValue, Is.EqualTo(expectedValue), field.Name);
                }
            }
        }

        private static void AssertEventEquality(object expected, object actual)
        {
            foreach (FieldInfo field in expected.GetType().GetFields())
            {
                object expectedValue = field.GetValue(expected);
                object actualValue = field.GetValue(actual);
                if (field.FieldType == typeof(Correlation))
                {
                    Assert.That(((Correlation)actualValue).Equals((Correlation)expectedValue), Is.True, field.Name);
                }
                else
                {
                    Assert.That(actualValue, Is.EqualTo(expectedValue), field.Name);
                }
            }
        }

        private static string Encode(string method, object dto)
        {
            return (string)typeof(Valera.VrGateway.Json.WireCodec).GetMethod(method, BindingFlags.Public | BindingFlags.Static).Invoke(null, new[] { dto });
        }

        private static object DecodeCommand(string json) { return Valera.VrGateway.Json.WireCodec.DecodeCommand(json); }
        private static object DecodeEvent(string json) { return Valera.VrGateway.Json.WireCodec.DecodeEvent(json); }
    }
}
