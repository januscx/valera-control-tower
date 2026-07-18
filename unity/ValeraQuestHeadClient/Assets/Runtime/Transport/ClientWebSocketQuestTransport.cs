using System;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Valera.QuestHeadClient.Transport
{
    public sealed class ClientWebSocketQuestTransport : IQuestTransport
    {
        private readonly SemaphoreSlim sendGate = new SemaphoreSlim(1, 1);
        private ClientWebSocket socket;

        public bool IsOpen => socket != null && socket.State == WebSocketState.Open;

        public async Task ConnectAsync(Uri endpoint, CancellationToken cancellationToken)
        {
            DisposeSocket();
            socket = new ClientWebSocket();
            await socket.ConnectAsync(endpoint, cancellationToken).ConfigureAwait(false);
        }

        public async Task SendAsync(string text, CancellationToken cancellationToken)
        {
            if (!IsOpen) throw new InvalidOperationException("WebSocket is not open.");
            byte[] bytes = Encoding.UTF8.GetBytes(text);
            await sendGate.WaitAsync(cancellationToken).ConfigureAwait(false);
            try
            {
                await socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cancellationToken).ConfigureAwait(false);
            }
            finally
            {
                sendGate.Release();
            }
        }

        public async Task<string> ReceiveAsync(CancellationToken cancellationToken)
        {
            if (!IsOpen) return null;
            using (var stream = new MemoryStream())
            {
                byte[] buffer = new byte[8192];
                WebSocketReceiveResult result;
                do
                {
                    result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), cancellationToken).ConfigureAwait(false);
                    if (result.MessageType == WebSocketMessageType.Close) return null;
                    stream.Write(buffer, 0, result.Count);
                }
                while (!result.EndOfMessage);
                return Encoding.UTF8.GetString(stream.ToArray());
            }
        }

        public async Task CloseAsync(CancellationToken cancellationToken)
        {
            if (IsOpen)
            {
                await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "client closing", cancellationToken).ConfigureAwait(false);
            }
            DisposeSocket();
        }

        public void Dispose()
        {
            DisposeSocket();
            sendGate.Dispose();
        }

        private void DisposeSocket()
        {
            if (socket != null)
            {
                socket.Dispose();
                socket = null;
            }
        }
    }
}
