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
            var target = new NeckTargetEventDto { schema_version = "0.1", event_type = "neck.target", gateway_monotonic_ns = 1, session_id = "session-1", sequence = 2, pan_degrees = 1.0, tilt_degrees = -2.0, hold = false };

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

        private static string Encode(string method, object dto)
        {
            return (string)typeof(Valera.VrGateway.Json.WireCodec).GetMethod(method, BindingFlags.Public | BindingFlags.Static).Invoke(null, new[] { dto });
        }

        private static object DecodeCommand(string json) { return Valera.VrGateway.Json.WireCodec.DecodeCommand(json); }
        private static object DecodeEvent(string json) { return Valera.VrGateway.Json.WireCodec.DecodeEvent(json); }
    }
}
