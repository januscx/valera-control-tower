using System;

namespace Valera.VrGateway.Session
{
    public sealed class SessionSequence
    {
        private long current;

        public SessionSequence(long currentValue)
        {
            if (currentValue < 0) throw new ArgumentOutOfRangeException(nameof(currentValue));
            current = currentValue;
        }

        public long Next()
        {
            if (current == long.MaxValue) throw new InvalidOperationException("Session sequence is exhausted.");
            current++;
            return current;
        }
    }
}
