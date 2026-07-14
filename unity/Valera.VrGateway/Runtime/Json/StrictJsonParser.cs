using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace Valera.VrGateway.Json
{
    public sealed class WireValidationException : Exception
    {
        public WireValidationException(string message) : base(message) { }
    }

    public enum JsonKind { Object, Array, String, Number, Boolean, Null }

    public sealed class JsonValue
    {
        public JsonKind kind;
        public Dictionary<string, JsonValue> members;
        public List<JsonValue> items;
        public string text;
        public bool boolean;
    }

    public static class StrictJsonParser
    {
        public const int MaximumCharacters = 65536;
        public const int MaximumBytes = 65536;
        public const int MaximumDepth = 16;

        public static JsonValue Parse(string json)
        {
            if (json == null) throw new WireValidationException("JSON must not be null.");
            if (json.Length > MaximumCharacters) throw new WireValidationException("JSON exceeds character limit.");
            try { if (new UTF8Encoding(false, true).GetByteCount(json) > MaximumBytes) throw new WireValidationException("JSON exceeds byte limit."); }
            catch (EncoderFallbackException) { throw new WireValidationException("JSON contains malformed Unicode."); }
            var parser = new Parser(json);
            JsonValue value = parser.ReadValue(0);
            parser.SkipWhitespace();
            if (!parser.AtEnd) throw new WireValidationException("JSON has trailing data.");
            return value;
        }

        private sealed class Parser
        {
            private readonly string source;
            private int index;
            internal Parser(string value) { source = value; }
            internal bool AtEnd { get { return index == source.Length; } }
            internal void SkipWhitespace() { while (!AtEnd && (source[index] == ' ' || source[index] == '\t' || source[index] == '\r' || source[index] == '\n')) index++; }

            internal JsonValue ReadValue(int depth)
            {
                if (depth > MaximumDepth) throw new WireValidationException("JSON nesting exceeds limit.");
                SkipWhitespace();
                if (AtEnd) throw new WireValidationException("JSON value is missing.");
                char c = source[index];
                if (c == '{') return ReadObject(depth + 1);
                if (c == '[') return ReadArray(depth + 1);
                if (c == '"') return new JsonValue { kind = JsonKind.String, text = ReadString() };
                if (c == 't') { ReadLiteral("true"); return new JsonValue { kind = JsonKind.Boolean, boolean = true }; }
                if (c == 'f') { ReadLiteral("false"); return new JsonValue { kind = JsonKind.Boolean, boolean = false }; }
                if (c == 'n') { ReadLiteral("null"); return new JsonValue { kind = JsonKind.Null }; }
                if (c == '-' || (c >= '0' && c <= '9')) return new JsonValue { kind = JsonKind.Number, text = ReadNumber() };
                throw new WireValidationException("Invalid JSON token.");
            }

            private JsonValue ReadObject(int depth)
            {
                index++;
                var members = new Dictionary<string, JsonValue>(StringComparer.Ordinal);
                SkipWhitespace();
                if (Consume('}')) return new JsonValue { kind = JsonKind.Object, members = members };
                while (true)
                {
                    SkipWhitespace();
                    if (AtEnd || source[index] != '"') throw new WireValidationException("Object property name is required.");
                    string name = ReadString();
                    if (members.ContainsKey(name)) throw new WireValidationException("Duplicate JSON property.");
                    members.Add(name, null);
                    SkipWhitespace();
                    Require(':');
                    members[name] = ReadValue(depth);
                    SkipWhitespace();
                    if (Consume('}')) return new JsonValue { kind = JsonKind.Object, members = members };
                    Require(',');
                }
            }

            private JsonValue ReadArray(int depth)
            {
                index++;
                var items = new List<JsonValue>();
                SkipWhitespace();
                if (Consume(']')) return new JsonValue { kind = JsonKind.Array, items = items };
                while (true)
                {
                    items.Add(ReadValue(depth));
                    SkipWhitespace();
                    if (Consume(']')) return new JsonValue { kind = JsonKind.Array, items = items };
                    Require(',');
                }
            }

            private string ReadString()
            {
                Require('"');
                var builder = new StringBuilder();
                while (!AtEnd)
                {
                    char c = source[index++];
                    if (c == '"') return builder.ToString();
                    if (c < 0x20) throw new WireValidationException("Control character in JSON string.");
                    if (c != '\\') { if (char.IsSurrogate(c)) throw new WireValidationException("Malformed Unicode surrogate."); builder.Append(c); continue; }
                    if (AtEnd) throw new WireValidationException("Incomplete JSON escape.");
                    char escape = source[index++];
                    switch (escape)
                    {
                        case '"': builder.Append('"'); break; case '\\': builder.Append('\\'); break; case '/': builder.Append('/'); break;
                        case 'b': builder.Append('\b'); break; case 'f': builder.Append('\f'); break; case 'n': builder.Append('\n'); break;
                        case 'r': builder.Append('\r'); break; case 't': builder.Append('\t'); break;
                        case 'u': builder.Append(ReadUnicodeEscape()); break;
                        default: throw new WireValidationException("Invalid JSON escape.");
                    }
                }
                throw new WireValidationException("Unterminated JSON string.");
            }

            private string ReadUnicodeEscape()
            {
                char first = ReadHexCodeUnit();
                if (!char.IsHighSurrogate(first))
                {
                    if (char.IsLowSurrogate(first)) throw new WireValidationException("Malformed Unicode surrogate.");
                    return first.ToString();
                }
                if (index + 2 > source.Length || source[index++] != '\\' || source[index++] != 'u') throw new WireValidationException("Malformed Unicode surrogate pair.");
                char second = ReadHexCodeUnit();
                if (!char.IsLowSurrogate(second)) throw new WireValidationException("Malformed Unicode surrogate pair.");
                return new string(new[] { first, second });
            }

            private char ReadHexCodeUnit()
            {
                if (index + 4 > source.Length) throw new WireValidationException("Incomplete Unicode escape.");
                int value = 0;
                for (int i = 0; i < 4; i++)
                {
                    char c = source[index++];
                    int digit = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
                    if (digit < 0) throw new WireValidationException("Invalid Unicode escape.");
                    value = (value << 4) | digit;
                }
                return (char)value;
            }

            private string ReadNumber()
            {
                int start = index;
                Consume('-');
                if (AtEnd) throw new WireValidationException("Invalid JSON number.");
                if (Consume('0')) { if (!AtEnd && char.IsDigit(source[index])) throw new WireValidationException("Invalid JSON number."); }
                else { RequireDigit(); while (!AtEnd && char.IsDigit(source[index])) index++; }
                if (Consume('.')) { RequireDigit(); while (!AtEnd && char.IsDigit(source[index])) index++; }
                if (!AtEnd && (source[index] == 'e' || source[index] == 'E')) { index++; if (!AtEnd && (source[index] == '+' || source[index] == '-')) index++; RequireDigit(); while (!AtEnd && char.IsDigit(source[index])) index++; }
                return source.Substring(start, index - start);
            }

            private void ReadLiteral(string literal) { for (int i = 0; i < literal.Length; i++) { if (AtEnd || source[index++] != literal[i]) throw new WireValidationException("Invalid JSON literal."); } }
            private bool Consume(char c) { if (!AtEnd && source[index] == c) { index++; return true; } return false; }
            private void Require(char c) { SkipWhitespace(); if (!Consume(c)) throw new WireValidationException("Expected JSON punctuation."); }
            private void RequireDigit() { if (AtEnd || !char.IsDigit(source[index])) throw new WireValidationException("Invalid JSON number."); index++; }
        }
    }
}
