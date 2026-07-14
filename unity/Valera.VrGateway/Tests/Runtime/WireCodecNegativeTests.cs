using System;
using System.Text;
using NUnit.Framework;
using Valera.VrGateway.Contracts;
using Valera.VrGateway.Json;

namespace Valera.VrGateway.Tests
{
    public sealed class WireCodecNegativeTests
    {
        private const string ValidSessionStart = "{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}";
        private const string ValidHeadPose = "{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":2,\"timestamp_ms\":1,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1}}}";
        private const string ValidModeSet = "{\"schema_version\":\"0.1\",\"command\":\"mode.set\",\"session_id\":\"s-1\",\"sequence\":2,\"timestamp_ms\":1,\"payload\":{\"mode\":\"head\"}}";
        private const string ValidGatewayState = "{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":1,\"state\":\"IDLE\",\"session_id\":null,\"sequence\":null}";
        private const string ValidNeckTarget = "{\"schema_version\":\"0.1\",\"event_type\":\"neck.target\",\"gateway_monotonic_ns\":1,\"session_id\":\"s-1\",\"sequence\":1,\"pan_degrees\":0,\"tilt_degrees\":0,\"hold\":false}";

        [Test]
        public void DecodeCommand_RejectsNullJson()
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(null));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0}")]
        [TestCase("{\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{}}")]
        public void DecodeCommand_RejectsMissingRootOrPayloadFields(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"extra\":true,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\",\"extra\":true}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1,\"extra\":1}}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1},\"position\":{\"x\":1,\"y\":2,\"z\":3,\"extra\":4}}}")]
        public void DecodeCommand_RejectsExtraFields(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\",\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"session_id\":\"s-1\",\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"mode.set\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"mode\":\"head\",\"mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1,\"x\":0}}}")]
        [TestCase("{\"x\":1,\"\\u0078\":2}")]
        public void DecodeCommand_RejectsDuplicateKeys(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":null,\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":null,\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":null,\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":null,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":null,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":null}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":\"1\",\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":\"invalid\"}")]
        public void DecodeCommand_RejectsNullOrWrongTokenTypes(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}} trailing")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}{\"schema_version\":\"0.1\"}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"},}")]
        [TestCase("{\"x\":1,}")]
        [TestCase("{/*comment*/\"schema_version\":\"0.1\"}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}//comment")]
        public void DecodeCommand_RejectsTrailingDataAndComments(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"\\\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"\\x\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"\\uD800\"}}")]
        public void DecodeCommand_RejectsMalformedStringsAndEscapes(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [Test]
        public void DecodeCommand_RejectsExcessiveLength()
        {
            string json = "{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"" + new string('a', 70000) + "\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}";
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":{\"x\":1}}}}}}}}}}}}}}}")]
        public void DecodeCommand_RejectsExcessiveDepth(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":01,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1.0,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1e0,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":1e3,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"},\"extra\":9223372036854775808}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":-1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":0,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":-1,\"payload\":{\"requested_mode\":\"head\"}}")]
        public void DecodeCommand_RejectsInvalidIntegerForms(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":NaN,\"y\":0,\"z\":0,\"w\":1}}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":Infinity,\"y\":0,\"z\":0,\"w\":1}}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":0}}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":0,\"y\":0,\"w\":1}}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":\"0\",\"y\":0,\"z\":0,\"w\":1}}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1},\"position\":{\"x\":NaN,\"y\":2,\"z\":3}}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"quest_local\",\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1},\"position\":{\"x\":1,\"y\":2}}}")]
        public void DecodeCommand_RejectsUnsafeQuaternionAndPosition(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":\"0.2\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"unknown\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        public void DecodeCommand_RejectsUnsupportedSchemaOrUnknownCommand(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"   \",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"mode.set\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"mode\":\"\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"mode.set\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"mode\":\"   \"}})")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"mode.set\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"mode\":null}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"mode.set\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"mode\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}}")]

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"drive\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"arm\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"unknown\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"head.pose\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"frame\":\"other\",\"orientation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1}}}")]
        public void DecodeCommand_RejectsUnsafeIdModeOrRequestedMode(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeCommand(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":1,\"state\":\"UNKNOWN\"}")]
        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"command.rejected\",\"gateway_monotonic_ns\":1,\"code\":\"BAD_CODE\",\"message\":\"m\"}")]
        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"safety.stop\",\"gateway_monotonic_ns\":1,\"reason\":\"BAD_REASON\",\"session_id\":null,\"sequence\":null,\"neck_action\":\"HOLD\",\"base_action\":\"STOP\",\"arm_action\":\"HOLD\"}")]
        public void DecodeEvent_RejectsUnknownEnumValues(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeEvent(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":1,\"state\":\"IDLE\",\"session_id\":\"s-1\",\"sequence\":null}")]
        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":1,\"state\":\"IDLE\",\"session_id\":null,\"sequence\":1}")]
        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"neck.target\",\"gateway_monotonic_ns\":1,\"session_id\":\"s-1\",\"sequence\":null,\"pan_degrees\":0,\"tilt_degrees\":0,\"hold\":false}")]
        public void DecodeEvent_RejectsPartialOrRequiredCorrelation(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeEvent(json));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":1}")]
        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"neck.target\",\"gateway_monotonic_ns\":1,\"session_id\":\"s-1\",\"sequence\":1,\"pan_degrees\":0,\"tilt_degrees\":0,\"hold\":false,\"extra\":true}")]
        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"unknown\",\"gateway_monotonic_ns\":1}")]
        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":-1,\"state\":\"IDLE\",\"session_id\":null,\"sequence\":null}")]
        public void DecodeEvent_RejectsInvalidEventShape(string json)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.DecodeEvent(json));
        }

        [TestCaseSource(nameof(InvalidCommandEncodeCases))]
        public void EncodeCommand_RejectsInvalidDto(object dto)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeCommand(dto));
        }

        [Test]
        public void EncodeCommand_ThrowsWireValidationExceptionForNullPayload()
        {
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeCommand(new SessionStartCommandDto { schema_version = "0.1", command = "session.start", session_id = "s-1", sequence = 1, timestamp_ms = 0, payload = null }));
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeCommand(new SessionStopCommandDto { schema_version = "0.1", command = "session.stop", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = null }));
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeCommand(new ModeSetCommandDto { schema_version = "0.1", command = "mode.set", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = null }));
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeCommand(new HeadPoseCommandDto { schema_version = "0.1", command = "head.pose", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = null }));
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeCommand(new HeadRecenterCommandDto { schema_version = "0.1", command = "head.recenter", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = null }));
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeCommand(new EmergencyStopCommandDto { schema_version = "0.1", command = "emergency_stop", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = null }));
        }

        [Test]
        public void EncodeCommand_ThrowsWireValidationExceptionForNullOrientation()
        {
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeCommand(new HeadPoseCommandDto { schema_version = "0.1", command = "head.pose", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new HeadPosePayloadDto { frame = "quest_local", orientation = null } }));
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeCommand(new HeadRecenterCommandDto { schema_version = "0.1", command = "head.recenter", session_id = "s-1", sequence = 2, timestamp_ms = 1, payload = new HeadRecenterPayloadDto { frame = "quest_local", orientation = null } }));
        }

        [TestCaseSource(nameof(InvalidEventEncodeCases))]
        public void EncodeEvent_RejectsInvalidDto(object dto)
        {
            Assert.Throws<WireValidationException>(() => WireCodec.EncodeEvent(dto));
        }

        private static object[] InvalidCommandEncodeCases()
        {
            return new object[]
            {
                new SessionStartCommandDto { schema_version = "0.1", command = "session.start", session_id = "s-1", sequence = 1, timestamp_ms = 0, payload = new SessionStartPayloadDto { requested_mode = "drive" } },
                new SessionStartCommandDto { schema_version = "0.1", command = "session.start", session_id = "s-1", sequence = 0, timestamp_ms = 0, payload = new SessionStartPayloadDto { requested_mode = "head" } },
                new ModeSetCommandDto { schema_version = "0.1", command = "mode.set", session_id = "s-1", sequence = 1, timestamp_ms = 0, payload = new ModeSetPayloadDto { mode = "" } },
                new ModeSetCommandDto { schema_version = "0.1", command = "mode.set", session_id = "s-1", sequence = 1, timestamp_ms = 0, payload = new ModeSetPayloadDto { mode = new string('a', 65) } },
                new HeadPoseCommandDto { schema_version = "0.1", command = "head.pose", session_id = "s-1", sequence = 1, timestamp_ms = 0, payload = new HeadPosePayloadDto { frame = "quest_local", orientation = new QuaternionDto { x = 0, y = 0, z = 0, w = 0 } } },
                new HeadPoseCommandDto { schema_version = "0.1", command = "head.pose", session_id = "s-1", sequence = 1, timestamp_ms = 0, payload = new HeadPosePayloadDto { frame = "other", orientation = new QuaternionDto { x = 0, y = 0, z = 0, w = 1 } } },
                new HeadPoseCommandDto { schema_version = "0.1", command = "head.pose", session_id = "s-1", sequence = 1, timestamp_ms = 0, payload = new HeadPosePayloadDto { frame = "quest_local", orientation = new QuaternionDto { x = double.NaN, y = 0, z = 0, w = 1 } } },
                new HeadPoseCommandDto { schema_version = "0.1", command = "head.pose", session_id = "s-1", sequence = 1, timestamp_ms = 0, payload = new HeadPosePayloadDto { frame = "quest_local", orientation = new QuaternionDto { x = 0, y = 0, z = 0, w = 1 }, position = new PositionDto { x = double.NaN, y = 0, z = 0 } } },
            };
        }

        private static object[] InvalidEventEncodeCases()
        {
            return new object[]
            {
                new GatewayStateEventDto { schema_version = "0.1", event_type = "gateway.state", gateway_monotonic_ns = 1, state = "UNKNOWN", correlation = Correlation.Unavailable },
                new NeckTargetEventDto { schema_version = "0.1", event_type = "neck.target", gateway_monotonic_ns = 1, correlation = Correlation.Unavailable, pan_degrees = 0, tilt_degrees = 0, hold = false },
                new SafetyStopEventDto { schema_version = "0.1", event_type = "safety.stop", gateway_monotonic_ns = 1, reason = "WATCHDOG", correlation = Correlation.Unavailable, neck_action = "", base_action = "STOP", arm_action = "HOLD" },
                new CommandRejectedEventDto { schema_version = "0.1", event_type = "command.rejected", gateway_monotonic_ns = 1, code = "UNKNOWN", message = "m", correlation = Correlation.Unavailable },
                new CommandRejectedEventDto { schema_version = "0.1", event_type = "command.rejected", gateway_monotonic_ns = 1, code = "UNKNOWN_MODE", message = "", correlation = Correlation.Unavailable },
                new NeckTargetEventDto { schema_version = "0.1", event_type = "neck.target", gateway_monotonic_ns = 1, correlation = new Correlation("s-1", 1), pan_degrees = double.NaN, tilt_degrees = 0, hold = false },
            };
        }
    }
}
