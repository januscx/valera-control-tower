using System;
using NUnit.Framework;
using UnityEngine;
using Valera.QuestHeadClient.Session;
using Valera.VrGateway.Contracts;
using Valera.VrGateway.Json;

namespace Valera.QuestHeadClient.Tests
{
    public sealed class QuestHeadSessionTests
    {
        private long clock;
        private QuestHeadSession session;

        [SetUp]
        public void SetUp()
        {
            clock = 1000;
            session = new QuestHeadSession(() => clock, () => "test-session");
        }

        [Test]
        public void PoseAndRecenterAreGatedByGatewayState()
        {
            session.StartSession();
            Assert.That(session.BuildPose(Quaternion.identity, clock), Is.Null);
            Assert.Throws<InvalidOperationException>(() => session.BuildRecenter(Quaternion.identity));

            session.HandleEvent(State("AWAITING_RECENTER", 1));
            Assert.That(session.CanRecenter, Is.True);
            session.BuildRecenter(Quaternion.identity);
            Assert.That(session.BuildPose(Quaternion.identity, clock), Is.Null);

            session.HandleEvent(State("HEAD_ACTIVE", 2));
            Assert.That(session.TryConsumePoseSlot(clock), Is.True);
            string pose = session.BuildPose(Quaternion.identity, clock);
            Assert.That(pose, Does.Contain("head.pose"));
            Assert.That(session.TryConsumePoseSlot(clock + 1), Is.False);
        }

        [Test]
        public void TimestampAndSequenceNeverMoveBackwards()
        {
            string start = session.StartSession();
            clock = 900;
            session.HandleEvent(State("AWAITING_RECENTER", 1));
            string recenter = session.BuildRecenter(Quaternion.identity);
            Assert.That(start, Does.Contain("timestamp_ms"));
            Assert.That(recenter, Does.Contain("head.recenter"));
        }

        [Test]
        public void RejectedAndMalformedEventsStopPoseStream()
        {
            session.StartSession();
            session.HandleEvent(State("HEAD_ACTIVE", 1));
            Assert.That(session.CanSendPose, Is.True);
            Assert.That(session.HandleEvent("not-json"), Is.False);
            Assert.That(session.CanSendPose, Is.False);
            Assert.That(session.BuildBestEffortStop(), Is.Not.Null);
        }

        private string State(string state, long sequence)
        {
            return WireCodec.EncodeEvent(new GatewayStateEventDto
            {
                schema_version = WireValues.SchemaVersion,
                event_type = WireValues.GatewayState,
                gateway_monotonic_ns = clock * 1000000,
                state = state,
                correlation = new Correlation("test-session", sequence),
            });
        }
    }
}
