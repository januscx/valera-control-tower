using System;
using System.Threading;
using System.Threading.Tasks;

namespace Valera.QuestHeadClient.Transport
{
    public interface IQuestTransport : IDisposable
    {
        bool IsOpen { get; }
        Task ConnectAsync(Uri endpoint, CancellationToken cancellationToken);
        Task SendAsync(string text, CancellationToken cancellationToken);
        Task<string> ReceiveAsync(CancellationToken cancellationToken);
        Task CloseAsync(CancellationToken cancellationToken);
    }
}
