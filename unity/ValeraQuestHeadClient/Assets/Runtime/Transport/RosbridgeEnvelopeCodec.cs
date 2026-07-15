using System;
using UnityEngine;

namespace Valera.QuestHeadClient.Transport
{
    public static class RosbridgeEnvelopeCodec
    {
        [Serializable]
        private sealed class StringMessage
        {
            public string data;
        }

        [Serializable]
        private sealed class Envelope
        {
            public string op;
            public string id;
            public string topic;
            public string type;
            public StringMessage msg;
        }

        public static string EncodeAdvertise(string topic, string type)
        {
            return JsonUtility.ToJson(new Envelope { op = "advertise", topic = topic, type = type });
        }

        public static string EncodeSubscribe(string topic)
        {
            return JsonUtility.ToJson(new Envelope { op = "subscribe", topic = topic });
        }

        public static string EncodePublish(string topic, string innerJson)
        {
            if (string.IsNullOrEmpty(topic)) throw new ArgumentException("Topic is required.", nameof(topic));
            if (innerJson == null) throw new ArgumentNullException(nameof(innerJson));
            return JsonUtility.ToJson(new Envelope
            {
                op = "publish",
                topic = topic,
                msg = new StringMessage { data = innerJson },
            });
        }

        public static string DecodeMessageData(string envelopeJson)
        {
            if (string.IsNullOrEmpty(envelopeJson)) throw new InvalidOperationException("Envelope is empty.");
            Envelope envelope = JsonUtility.FromJson<Envelope>(envelopeJson);
            if (envelope == null || envelope.op != "publish" || envelope.msg == null || envelope.msg.data == null)
            {
                throw new InvalidOperationException("Expected a rosbridge publish envelope with msg.data.");
            }
            return envelope.msg.data;
        }
    }
}
