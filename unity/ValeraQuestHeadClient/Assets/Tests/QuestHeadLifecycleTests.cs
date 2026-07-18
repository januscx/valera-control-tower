using NUnit.Framework;
using Valera.QuestHeadClient.Session;
using Valera.QuestHeadClient.Transport;

namespace Valera.QuestHeadClient.Tests
{
    public sealed class QuestHeadLifecycleTests
    {
        [Test]
        public void CleanupGateAllowsExactlyOneCleanupAndThenReconnect()
        {
            var gate = new TransportCleanupGate();
            Assert.That(gate.TryClaim(), Is.True);
            Assert.That(gate.TryClaim(), Is.False);
            gate.Release();
            Assert.That(gate.TryClaim(), Is.True);
        }

        [Test]
        public void SessionCanCloseAndStartAgainWithFreshState()
        {
            var session = new QuestHeadSession(() => 1000, () => "fresh-session");
            session.StartSession();
            session.Close();
            Assert.That(session.State, Is.EqualTo(QuestHeadClientState.Disconnected));
            session.StartSession();
            Assert.That(session.State, Is.EqualTo(QuestHeadClientState.Connecting));
        }
    }
}
