using System.Threading;

namespace Valera.QuestHeadClient.Transport
{
    public sealed class TransportCleanupGate
    {
        private int claimed;

        public bool IsAvailable => Volatile.Read(ref claimed) == 0;

        public bool TryClaim()
        {
            return Interlocked.Exchange(ref claimed, 1) == 0;
        }

        public void Release()
        {
            Volatile.Write(ref claimed, 0);
        }
    }
}
