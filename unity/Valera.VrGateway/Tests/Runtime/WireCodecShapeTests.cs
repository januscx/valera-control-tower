using NUnit.Framework;
using Valera.VrGateway.Contracts;
using Valera.VrGateway.Json;

namespace Valera.VrGateway.Tests
{
    public sealed class WireCodecShapeTests
    {
        [Test]
        public void EncodeCommand_SessionStart_ExactShape()
        {
            var dto = new SessionStartCommandDto
            {
                schema_version = "0.1",
                command = "session.start",
                session_id = "s-1",
                sequence = 1,
                timestamp_ms = 0,
                payload = new SessionStartPayloadDto { requested_mode = "head" },
            };
            string json = WireCodec.EncodeCommand(dto);
            Assert.That(json, Is.EqualTo("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}"));
        }

        [Test]
        public void EncodeCommand_ModeSet_ExactShape()
        {
            var dto = new ModeSetCommandDto
            {
                schema_version = "0.1",
                command = "mode.set",
                session_id = "s-1",
                sequence = 2,
                timestamp_ms = 1,
                payload = new ModeSetPayloadDto { mode = "inspection" },
            };
            string json = WireCodec.EncodeCommand(dto);
            Assert.That(json, Is.EqualTo("{\"schema_version\":\"0.1\",\"command\":\"mode.set\",\"session_id\":\"s-1\",\"sequence\":2,\"timestamp_ms\":1,\"payload\":{\"mode\":\"inspection\"}}"));
        }

        [Test]
        public void EncodeCommand_HeadPoseWithoutPosition_OmitsPosition()
        {
            var dto = new HeadPoseCommandDto
            {
                schema_version = "0.1",
                command = "head.pose",
                session_id = "s-1",
                sequence = 2,
                timestamp_ms = 1,
                payload = new HeadPosePayloadDto { frame = "quest_local", orientation = new QuaternionDto { x = 0, y = 0, z = 0, w = 1 } },
            };
            string json = WireCodec.EncodeCommand(dto);
            Assert.That(json, Does.Not.Contain("position"));
            Assert.That(json, Does.Contain("\"frame\":\"quest_local\""));
            Assert.That(json, Does.Contain("\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1}"));
        }

        [Test]
        public void EncodeCommand_HeadPoseWithPosition_IncludesPosition()
        {
            var dto = new HeadPoseCommandDto
            {
                schema_version = "0.1",
                command = "head.pose",
                session_id = "s-1",
                sequence = 2,
                timestamp_ms = 1,
                payload = new HeadPosePayloadDto
                {
                    frame = "quest_local",
                    orientation = new QuaternionDto { x = 0, y = 0, z = 0, w = 1 },
                    position = new PositionDto { x = 1, y = 2, z = 3 },
                },
            };
            string json = WireCodec.EncodeCommand(dto);
            Assert.That(json, Is.EqualTo("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":2,\"timestamp_ms\":1,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1},\"position\":{\"x\":1,\"y\":2,\"z\":3}}}"));
        }

        [Test]
        public void EncodeCommand_EmergencyStop_ExactShape()
        {
            var dto = new EmergencyStopCommandDto
            {
                schema_version = "0.1",
                command = "emergency_stop",
                session_id = "s-1",
                sequence = 2,
                timestamp_ms = 1,
                payload = new EmptyPayloadDto(),
            };
            string json = WireCodec.EncodeCommand(dto);
            Assert.That(json, Is.EqualTo("{\"schema_version\":\"0.1\",\"command\":\"emergency_stop\",\"session_id\":\"s-1\",\"sequence\":2,\"timestamp_ms\":1,\"payload\":{}}"));
        }

        [Test]
        public void EncodeEvent_GatewayStateUncorrelated_EmitsNullIdentifiers()
        {
            var dto = new GatewayStateEventDto
            {
                schema_version = "0.1",
                event_type = "gateway.state",
                gateway_monotonic_ns = 1,
                state = "IDLE",
                correlation = Correlation.Unavailable,
            };
            string json = WireCodec.EncodeEvent(dto);
            Assert.That(json, Is.EqualTo("{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":1,\"state\":\"IDLE\",\"session_id\":null,\"sequence\":null}"));
        }

        [Test]
        public void EncodeEvent_NeckTarget_ExactShape()
        {
            var dto = new NeckTargetEventDto
            {
                schema_version = "0.1",
                event_type = "neck.target",
                gateway_monotonic_ns = 1,
                correlation = new Correlation("s-1", 2),
                pan_degrees = 1.0,
                tilt_degrees = -2.0,
                hold = false,
            };
            string json = WireCodec.EncodeEvent(dto);
            Assert.That(json, Is.EqualTo("{\"schema_version\":\"0.1\",\"event_type\":\"neck.target\",\"gateway_monotonic_ns\":1,\"session_id\":\"s-1\",\"sequence\":2,\"pan_degrees\":1,\"tilt_degrees\":-2,\"hold\":false}"));
        }

        [Test]
        public void EncodeEvent_SafetyStop_ExactShape()
        {
            var dto = new SafetyStopEventDto
            {
                schema_version = "0.1",
                event_type = "safety.stop",
                gateway_monotonic_ns = 1,
                reason = "WATCHDOG",
                correlation = Correlation.Unavailable,
                neck_action = "HOLD_LAST_POSITION",
                base_action = "STOP",
                arm_action = "HOLD",
            };
            string json = WireCodec.EncodeEvent(dto);
            Assert.That(json, Is.EqualTo("{\"schema_version\":\"0.1\",\"event_type\":\"safety.stop\",\"gateway_monotonic_ns\":1,\"reason\":\"WATCHDOG\",\"session_id\":null,\"sequence\":null,\"neck_action\":\"HOLD_LAST_POSITION\",\"base_action\":\"STOP\",\"arm_action\":\"HOLD\"}"));
        }

        [Test]
        public void EncodeEvent_CommandRejected_ExactShape()
        {
            var dto = new CommandRejectedEventDto
            {
                schema_version = "0.1",
                event_type = "command.rejected",
                gateway_monotonic_ns = 1,
                code = "UNKNOWN_MODE",
                message = "Requested mode is not recognized.",
                correlation = new Correlation("s-1", 2),
            };
            string json = WireCodec.EncodeEvent(dto);
            Assert.That(json, Is.EqualTo("{\"schema_version\":\"0.1\",\"event_type\":\"command.rejected\",\"gateway_monotonic_ns\":1,\"code\":\"UNKNOWN_MODE\",\"message\":\"Requested mode is not recognized.\",\"session_id\":\"s-1\",\"sequence\":2}"));
        }

        [Test]
        public void EncodeEvent_StringEscapesQuotesAndBackslash()
        {
            var dto = new CommandRejectedEventDto
            {
                schema_version = "0.1",
                event_type = "command.rejected",
                gateway_monotonic_ns = 1,
                code = "INVALID_PAYLOAD",
                message = "Say \"hello\" and \\back\\.",
                correlation = Correlation.Unavailable,
            };
            string json = WireCodec.EncodeEvent(dto);
            Assert.That(json, Does.Contain("\"message\":\"Say \\\"hello\\\" and \\\\back\\\\.\""));
        }
    }
}
