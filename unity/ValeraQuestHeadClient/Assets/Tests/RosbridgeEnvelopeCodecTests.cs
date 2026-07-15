using NUnit.Framework;
using Valera.QuestHeadClient.Transport;

namespace Valera.QuestHeadClient.Tests
{
    public sealed class RosbridgeEnvelopeCodecTests
    {
        [Test]
        public void PublishUsesStringMessageDataEnvelope()
        {
            string envelope = RosbridgeEnvelopeCodec.EncodePublish("/valera/vr_gateway/command", "{\"command\":\"session.start\"}");
            StringAssert.Contains("msg", envelope);
            StringAssert.Contains("data", envelope);
            StringAssert.Contains("session.start", RosbridgeEnvelopeCodec.DecodeMessageData(envelope));
        }

        [Test]
        public void AdvertiseAndSubscribeUseOnlyGatewayTopics()
        {
            StringAssert.Contains("/valera/vr_gateway/command", RosbridgeEnvelopeCodec.EncodeAdvertise("/valera/vr_gateway/command", "std_msgs/msg/String"));
            StringAssert.Contains("/valera/vr_gateway/event", RosbridgeEnvelopeCodec.EncodeSubscribe("/valera/vr_gateway/event"));
        }
    }
}
