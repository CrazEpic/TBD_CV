using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

public static class MiniJSON
{
    public static object Deserialize(string json)
    {
        if (json == null)
        {
            return null;
        }

        return Parser.Parse(json);
    }

    sealed class Parser : IDisposable
    {
        const string WORD_BREAK = "{}[],:\"";

        StringReader json;

        Parser(string jsonString)
        {
            json = new StringReader(jsonString);
        }

        public static object Parse(string jsonString)
        {
            using (var instance = new Parser(jsonString))
            {
                return instance.ParseValue();
            }
        }

        public void Dispose()
        {
            json.Dispose();
            json = null;
        }

        enum TOKEN
        {
            NONE,
            CURLY_OPEN,
            CURLY_CLOSE,
            SQUARED_OPEN,
            SQUARED_CLOSE,
            COLON,
            COMMA,
            STRING,
            NUMBER,
            TRUE,
            FALSE,
            NULL
        }

        Dictionary<string, object> ParseObject()
        {
            var table = new Dictionary<string, object>();
            json.Read();

            while (true)
            {
                switch (NextToken)
                {
                    case TOKEN.NONE:
                        return null;
                    case TOKEN.COMMA:
                        continue;
                    case TOKEN.CURLY_CLOSE:
                        return table;
                    default:
                    {
                        string name = ParseString();
                        if (name == null)
                        {
                            return null;
                        }

                        if (NextToken != TOKEN.COLON)
                        {
                            return null;
                        }
                        json.Read();

                        table[name] = ParseValue();
                        break;
                    }
                }
            }
        }

        List<object> ParseArray()
        {
            var array = new List<object>();
            json.Read();

            bool parsing = true;
            while (parsing)
            {
                TOKEN nextToken = NextToken;

                switch (nextToken)
                {
                    case TOKEN.NONE:
                        return null;
                    case TOKEN.COMMA:
                        continue;
                    case TOKEN.SQUARED_CLOSE:
                        parsing = false;
                        break;
                    default:
                        array.Add(ParseByToken(nextToken));
                        break;
                }
            }

            return array;
        }

        object ParseValue()
        {
            TOKEN nextToken = NextToken;
            return ParseByToken(nextToken);
        }

        object ParseByToken(TOKEN token)
        {
            switch (token)
            {
                case TOKEN.STRING:
                    return ParseString();
                case TOKEN.NUMBER:
                    return ParseNumber();
                case TOKEN.CURLY_OPEN:
                    return ParseObject();
                case TOKEN.SQUARED_OPEN:
                    return ParseArray();
                case TOKEN.TRUE:
                    return true;
                case TOKEN.FALSE:
                    return false;
                case TOKEN.NULL:
                    return null;
                default:
                    return null;
            }
        }

        string ParseString()
        {
            var s = new StringBuilder();
            json.Read();

            bool parsing = true;
            while (parsing)
            {
                if (json.Peek() == -1)
                {
                    break;
                }

                char c = NextChar;
                switch (c)
                {
                    case '"':
                        parsing = false;
                        break;
                    case '\\':
                    {
                        if (json.Peek() == -1)
                        {
                            parsing = false;
                            break;
                        }

                        c = NextChar;
                        switch (c)
                        {
                            case '"':
                            case '\\':
                            case '/':
                                s.Append(c);
                                break;
                            case 'b':
                                s.Append('\b');
                                break;
                            case 'f':
                                s.Append('\f');
                                break;
                            case 'n':
                                s.Append('\n');
                                break;
                            case 'r':
                                s.Append('\r');
                                break;
                            case 't':
                                s.Append('\t');
                                break;
                            case 'u':
                            {
                                var hex = new char[4];
                                for (int i = 0; i < 4; i++)
                                {
                                    hex[i] = NextChar;
                                }
                                s.Append((char)Convert.ToInt32(new string(hex), 16));
                                break;
                            }
                        }
                        break;
                    }
                    default:
                        s.Append(c);
                        break;
                }
            }

            return s.ToString();
        }

        object ParseNumber()
        {
            string number = NextWord;
            if (number.IndexOf('.') == -1)
            {
                if (long.TryParse(number, NumberStyles.Any, CultureInfo.InvariantCulture, out long parsedInt))
                {
                    return parsedInt;
                }
                return 0L;
            }

            if (double.TryParse(number, NumberStyles.Any, CultureInfo.InvariantCulture, out double parsedDouble))
            {
                return parsedDouble;
            }
            return 0.0;
        }

        void EatWhitespace()
        {
            while (char.IsWhiteSpace(PeekChar))
            {
                json.Read();
                if (json.Peek() == -1)
                {
                    break;
                }
            }
        }

        char PeekChar
        {
            get
            {
                int peek = json.Peek();
                return peek == -1 ? '\0' : Convert.ToChar(peek);
            }
        }

        char NextChar
        {
            get
            {
                int next = json.Read();
                return next == -1 ? '\0' : Convert.ToChar(next);
            }
        }

        string NextWord
        {
            get
            {
                var word = new StringBuilder();

                while (!IsWordBreak(PeekChar))
                {
                    word.Append(NextChar);
                    if (json.Peek() == -1)
                    {
                        break;
                    }
                }

                return word.ToString();
            }
        }

        TOKEN NextToken
        {
            get
            {
                EatWhitespace();

                if (json.Peek() == -1)
                {
                    return TOKEN.NONE;
                }

                switch (PeekChar)
                {
                    case '{':
                        return TOKEN.CURLY_OPEN;
                    case '}':
                        json.Read();
                        return TOKEN.CURLY_CLOSE;
                    case '[':
                        return TOKEN.SQUARED_OPEN;
                    case ']':
                        json.Read();
                        return TOKEN.SQUARED_CLOSE;
                    case ',':
                        json.Read();
                        return TOKEN.COMMA;
                    case '"':
                        return TOKEN.STRING;
                    case ':':
                        return TOKEN.COLON;
                    case '0':
                    case '1':
                    case '2':
                    case '3':
                    case '4':
                    case '5':
                    case '6':
                    case '7':
                    case '8':
                    case '9':
                    case '-':
                        return TOKEN.NUMBER;
                }

                switch (NextWord)
                {
                    case "false":
                        return TOKEN.FALSE;
                    case "true":
                        return TOKEN.TRUE;
                    case "null":
                        return TOKEN.NULL;
                }

                return TOKEN.NONE;
            }
        }

        static bool IsWordBreak(char c)
        {
            return char.IsWhiteSpace(c) || WORD_BREAK.IndexOf(c) != -1;
        }
    }
}
