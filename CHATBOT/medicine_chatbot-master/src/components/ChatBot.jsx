import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { FiSend, FiUser } from "react-icons/fi";
import { RiRobot2Line } from "react-icons/ri";
import Navbar from "./Navbar";

const ChatBot = () => {
    const [messages, setMessages] = useState([
        { id: 1, text: "Hello! How can I help you today?", sender: "bot", timestamp: new Date() }
    ]);
    const [inputMessage, setInputMessage] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSendMessage = async () => {
        if (!inputMessage.trim() || isTyping) return; // Prevent multiple sends

        const userMessage = inputMessage; // Store message before clearing input
        
        const newMessage = {
            id: messages.length + 1,
            text: userMessage,
            sender: "user",
            timestamp: new Date()
        };

        setMessages(prev => [...prev, newMessage]);
        setInputMessage("");
        setIsTyping(true);

        // 💡 MODIFICATION: Get user_id from localStorage
        const userId = localStorage.getItem("user_id"); 
        
        try {
            const response = await fetch(`http://localhost:8000/chat?question=${encodeURIComponent(userMessage)}`, {
                method: "GET",
                headers: {
                    // 💡 MODIFICATION: Pass user_id in a custom header
                    "X-User-ID": userId || "", 
                    "Content-Type": "application/json"
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            const botResponse = {
                id: messages.length + 2,
                text: data.reply || "Sorry, I couldn't process your request.",
                sender: "bot",
                timestamp: new Date()
            };

            // Use a functional update to ensure we're adding the bot message after the user message state is finalized
            setMessages(prev => [...prev, botResponse]);
        } catch (error) {
            console.error("Error fetching response:", error);
            setMessages(prev => [...prev, {
                id: messages.length + 2,
                text: "There was an error processing your request. Please try again or check the server status.",
                sender: "bot",
                timestamp: new Date()
            }]);
        } finally {
            setIsTyping(false);
        }
    };


    const handleKeyPress = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    const formatTime = (date) => {
        return new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    };

    return (
        <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900">
            <Navbar />
            
            {/* Header */}
            <div className="bg-white dark:bg-gray-800 shadow-md p-4 flex items-center space-x-3">
                <RiRobot2Line className="text-blue-500 text-2xl" />
                <div>
                    <h1 className="text-lg font-semibold text-gray-800 dark:text-white">Health Assistant</h1>
                    <p className="text-sm text-gray-500 dark:text-gray-400">AI converation tool</p>
                
                </div>
            </div>

            {/* Messages Container */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}
                    >
                        <div
                            className={`flex items-start space-x-2 max-w-[75%] ${
                                message.sender === "user" ? "flex-row-reverse space-x-reverse" : "flex-row"
                            }`}
                        >
                            <div
                                className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                    message.sender === "user" ? "bg-blue-500" : "bg-gray-200 dark:bg-gray-700"
                                }`}
                            >
                                {message.sender === "user" ? (
                                    <FiUser className="text-white" />
                                ) : (
                                    <RiRobot2Line className="text-gray-600 dark:text-gray-300" />
                                )}
                            </div>
                            <div
                                className={`rounded-lg p-3 ${
                                    message.sender === "user"
                                        ? "bg-blue-500 text-white"
                                        : "bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200"
                                } shadow-sm`}
                            >
                                <p className="text-sm">{message.text}</p>
                                <p className="text-xs mt-1 opacity-70">{formatTime(message.timestamp)}</p>
                            </div>
                        </div>
                    </div>
                ))}
                {isTyping && (
                    <div className="flex items-center space-x-2">
                        <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
                            <RiRobot2Line className="text-gray-600 dark:text-gray-300" />
                        </div>
                        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 shadow-sm">
                            <div className="flex space-x-1">
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }} />
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="bg-white dark:bg-gray-800 border-t dark:border-gray-700 p-4">
                <div className="max-w-4xl mx-auto flex items-end space-x-4">
                    <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-lg">
                        <textarea
                            value={inputMessage}
                            onChange={(e) => setInputMessage(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="Type your question about drugs or health..."
                            className="w-full bg-transparent border-0 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none dark:text-white"
                            rows="1"
                            style={{ minHeight: "44px", maxHeight: "200px" }}
                        />
                    </div>
                    <button
                        onClick={handleSendMessage}
                        disabled={!inputMessage.trim() || isTyping} // Disable when empty or typing
                        className={`rounded-lg p-3 flex items-center justify-center transition-colors duration-200 ${
                            !inputMessage.trim() || isTyping 
                                ? "bg-gray-400 cursor-not-allowed" 
                                : "bg-blue-500 hover:bg-blue-600 text-white"
                        }`}
                        aria-label="Send message"
                    >
                        <FiSend className="text-lg" />
                    </button>
                    
                </div>
            </div>
        </div>
    );
};

export default ChatBot;