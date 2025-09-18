import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import '../App.css'; // Make sure you have the required CSS
import Navbar from './Navbar'; // Assuming you have a Navbar component
import { FaThumbsUp, FaThumbsDown } from 'react-icons/fa';
// !!! WARNING: HARDCODING SECRETS IS NOT RECOMMENDED FOR PRODUCTION !!!
const API_TOKEN = "yksuthar@h46sg3qe7665"; // <-- REPLACE THIS PLACEHOLDER

// --- API Configuration ---
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const BASE_WS_URL = `${wsProtocol}//${window.location.host}/api/consumer/v1/completions`;
const FEEDBACK_BATCH_API_URL = '/api/backend/api/responses/batch';// <-- ENSURE THIS IS YOUR BATCH ENDPOINT

export default function Dashboard() {
  // --- State Management ---
  const [messages, setMessages] = useState(() => {
        // Try to get messages from localStorage
        const savedMessages = localStorage.getItem('chat_messages');
        // If we found saved messages, parse them back into an array
        if (savedMessages) {
          return JSON.parse(savedMessages);
        }
        // Otherwise, return the default initial message
        return [
          {
            id: 1,
            type: 'assistant',
            content: "Hello! I'm your AI assistant. How can I help you today?",
            feedback: null,
          },
        ];
      });
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionAttempts, setConnectionAttempts] = useState(0);

  // --- NEW: State for batching feedback and tracking request parameters ---
  const [feedbackQueue, setFeedbackQueue] = useState([]);
  const [lastRequestPayload, setLastRequestPayload] = useState(null);

  // --- Refs ---
  const socketRef = useRef(null);
  const messagesEndRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  // --- WebSocket Connection Logic ---
  const connectWebSocket = (token) => {
    if (!token || token === 'YOUR_HARDCODED_API_TOKEN_HERE') {
      console.error('API token is missing. Please set a valid token.');
      return;
    }

    if (socketRef.current) {
      socketRef.current.close();
    }

    const wsUrlWithToken = `${BASE_WS_URL}?token=${token}`;
    console.log('Attempting to connect to WebSocket...');
    socketRef.current = new WebSocket(wsUrlWithToken);

    socketRef.current.onopen = () => {
      console.log('WebSocket connected successfully.');
      setIsConnected(true);
      setConnectionAttempts(0);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };

    socketRef.current.onclose = () => {
      console.log('WebSocket closed.');
      setIsConnected(false);
      setIsLoading(false);
      if (connectionAttempts < 5) {
        const delay = Math.min(1000 * Math.pow(2, connectionAttempts), 10000);
        console.log(`Reconnecting in ${delay}ms...`);
        reconnectTimeoutRef.current = setTimeout(() => {
          setConnectionAttempts(prev => prev + 1);
          connectWebSocket(token);
        }, delay);
      } else {
        console.error('Max WebSocket reconnection attempts reached.');
      }
    };

    socketRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
      setIsLoading(false);
    };

    socketRef.current.onmessage = (event) => {
      if (event.data === '[DONE]') {
        setIsLoading(false);
        return;
      }

      try {
        const data = JSON.parse(event.data);
        if (data.error) {
          throw new Error(data.error);
        }

        if (data.choices && data.choices[0] && data.choices[0].text) {
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage && lastMessage.type === 'assistant' && lastMessage.loading) {
              // Append to the existing assistant message stream
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...lastMessage,
                content: lastMessage.content + data.choices[0].text,
              };
              return updated;
            } else {
              // Create a new assistant message for the first chunk
              const userPromptMessage = prev.find(p => p.type === 'user' && p.id === lastRequestPayload?.request_id) || prev[prev.length - 1];
              return [
                ...prev,
                {
                  id: data.id || Date.now(),
                  type: 'assistant',
                  content: data.choices[0].text,
                  loading: true,
                  feedback: null,
                  promptContent: userPromptMessage.content,
                  // Attach the parameters from the last request
                  requestDetails: {
                    model: lastRequestPayload?.model,
                    temperature: lastRequestPayload?.temperature,
                    max_tokens: lastRequestPayload?.max_tokens,
                  },
                },
              ];
            }
          });
        }
      } catch (err) {
        console.error('Error processing message:', err);
        setIsLoading(false);
      }
    };
  };

  // --- Message Handling ---
  
const handleSend = (e) => {
  e.preventDefault();
  if (!inputValue.trim() || !isConnected || isLoading) return;

  // --- START OF CHANGES ---

  // 1. Format the existing message history into a string.
  // We map over the messages, assign a role, and join them.
  // We use `slice(1)` to exclude the initial "Hello!" greeting from the context.
  const history = messages
    .slice(1)
    .map(msg => {
      const role = msg.type === 'user' ? 'User' : 'Assistant';
      return `${role}: ${msg.content}`;
    })
    .join('\n\n'); // Use double newlines for clear separation

  // 2. Create the full prompt by appending the new user input to the history.
  const fullPrompt = `${history}\n\nUser: ${inputValue.trim()}`;

  const userMessage = {
    id: Date.now(),
    type: 'user',
    content: inputValue.trim(),
  };

  const payload = {
    prompt: fullPrompt, // <-- Use the new prompt with full context
    model: 'my-quantized-model',
    max_tokens: 150,
    temperature: 0.7,
    request_id: String(userMessage.id),
    stream: true
  };

  // --- END OF CHANGES ---

  // The rest of the function remains the same
  setLastRequestPayload(payload);
  setMessages((prev) => [...prev, userMessage]);
  setInputValue('');
  setIsLoading(true);
  socketRef.current.send(JSON.stringify(payload));
};

  // --- Feedback Handling (Batching Logic) ---
  const handleFeedback = (messageId, feedbackType) => {
    const targetMessage = messages.find(msg => msg.id === messageId);
    if (!targetMessage || targetMessage.feedback) return;

    // Update UI immediately to show selection
    setMessages(prev => prev.map(msg =>
      msg.id === messageId ? { ...msg, feedback: feedbackType } : msg
    ));

    // If 'liked', add the data to the batch queue
    if (feedbackType === 'like') {
      const feedbackData = {
        prompt: targetMessage.promptContent,
        response: targetMessage.content,
        // Add the captured parameters
        model: targetMessage.requestDetails?.model,
        temperature: targetMessage.requestDetails?.temperature,
        max_tokens: targetMessage.requestDetails?.max_tokens,
      };
      setFeedbackQueue(prevQueue => [...prevQueue, feedbackData]);
    }
  };

  // --- Effects ---

  // Effect for WebSocket connection lifecycle
  useEffect(() => {
    connectWebSocket(API_TOKEN);
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) socketRef.current.close();
    };
  }, []); // Runs once on mount

  // Effect to finalize message loading state
  useEffect(() => {
    if (!isLoading) {
      setMessages(prev => prev.map(msg => msg.loading ? { ...msg, loading: false } : msg));
    }
  }, [isLoading]);

  useEffect(() => {
    // We stringify the array because localStorage can only store strings
    localStorage.setItem('chat_messages', JSON.stringify(messages));
  }, [messages]);


  // --- NEW: Effect for sending the feedback batch ---
  useEffect(() => {
    const sendFeedbackBatch = () => {
      if (feedbackQueue.length === 0) return;

      console.log(`Sending batch of ${feedbackQueue.length} feedback items.`);
      const payload = JSON.stringify(feedbackQueue);

      // Use sendBeacon for reliable data transmission on page unload
      if (navigator.sendBeacon) {
        navigator.sendBeacon(FEEDBACK_BATCH_API_URL, payload);
      } else {
        // Fallback for older browsers
        fetch(FEEDBACK_BATCH_API_URL, {
            method: 'POST',
            body: payload,
            headers: { 'Content-Type': 'application/json' },
            keepalive: true
        });
      }
      // Clear the queue after attempting to send
      setFeedbackQueue([]);
    };

    // Send when the user navigates away
    window.addEventListener('beforeunload', sendFeedbackBatch);
    // Send periodically as a fallback
    const intervalId = setInterval(sendFeedbackBatch, 60000); // Every 60 seconds

    return () => {
      window.removeEventListener('beforeunload', sendFeedbackBatch);
      clearInterval(intervalId);
      // Attempt one last send on component unmount
      sendFeedbackBatch();
    };
  }, [feedbackQueue]); // Re-runs when the queue changes

  // --- Sub-components & Render Logic ---
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) handleSend(e);
  };
  
  const MarkdownMessage = ({ content }) => (
    <ReactMarkdown
      components={{
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          return !inline ? (
            <SyntaxHighlighter style={oneDark} language={match ? match[1] : "plaintext"} PreTag="div" {...props}>
              {String(children).replace(/\n$/, '')}
            </SyntaxHighlighter>
          ) : (
            <code className={className} {...props}>{children}</code>
          );
        }
      }}
    >
      {content}
    </ReactMarkdown>
  );

  return (
    <div className="chat-board">
      <Navbar />
      <div className="chat-section">
        <div className="chat-messages-container">
            <div className="center-message">
              {messages.map((message) => (
                <div key={message.id} className={`message ${message.type}`}>
                  <div className="message-content animate">
                    <MarkdownMessage content={message.content} />
                    {/* Feedback Buttons: Show for completed assistant messages with prompt info */}
                    {message.type === 'assistant' && !message.loading && message.promptContent && (
                      <div className="feedback-buttons">
                      <button
                        className={`feedback-btn ${message.feedback === 'like' ? 'selected' : ''}`}
                        onClick={() => handleFeedback(message.id, 'like')}
                        disabled={!!message.feedback}
                        title="Like response"
                      >
                        <FaThumbsUp size={20} /> {/* Use the icon component */}
                      </button>
                      <button
                        className={`feedback-btn ${message.feedback === 'dislike' ? 'selected' : ''}`}
                        onClick={() => handleFeedback(message.id, 'dislike')}
                        disabled={!!message.feedback}
                        title="Dislike response"
                      >
                        <FaThumbsDown size={20} /> {/* Use the icon component */}
                      </button>
                    </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="message assistant">
                  <div className="message-content">
                    <div className="typing-indicator"><span></span><span></span><span></span></div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
        </div>
      </div>

      <div className="llm-input-form">
        <div className="llm-input-container">
          <input
            className="llm-input"
            type="text"
            placeholder={isConnected ? "Message AI Assistant..." : "Connecting..."}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading || !isConnected}
          />
          <button
            className="llm-send-btn"
            type="button"
            onClick={handleSend}
            disabled={isLoading || !inputValue.trim() || !isConnected}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 2L11 13" /><path d="M22 2L15 22L11 13L2 9L22 2Z" /></svg>
          </button>
        </div>
      </div>
    </div>
  );
}
