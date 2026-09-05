import { useEffect, useRef, useState } from "react";

import {
  Search,
  LogOut,
  MessageCircle,
  ArrowLeft,
  Send,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";

import {
  getConversations,
  getMessages} from "../services/conversationService";


function Chat() {

  const {
    user,
    logout,} = useAuth();

    // =========================
    // WEBSOCKET
    // =========================

    const websocketRef = useRef(null);
    const [socketConnected, setSocketConnected] = useState(false);

    // =========================
  // PRESENCE WEBSOCKET
  // =========================

  const presenceWebsocketRef = useRef(null);
  const [presenceConnected, setPresenceConnected] = useState(false);
  const [otherUserOnline, setOtherUserOnline] = useState(false);

    // =========================
  // TYPING
  // =========================

  const typingSentRef = useRef(false);
  const typingTimeoutRef = useRef(null);
  const lastReadMessageRef =useRef(null);
  const [typingUserId, setTypingUserId] = useState(null);

  // =========================
  // CONVERSATIONS
  // =========================

  const [
    conversations,
    setConversations,
  ] = useState([]);

  const [
    loadingConversations,
    setLoadingConversations,
  ] = useState(true);

  const [
    conversationError,
    setConversationError,
  ] = useState("");

  const [
    search,
    setSearch,
  ] = useState("");


  // =========================
  // SELECTED CONVERSATION
  // =========================

  const [
    selectedConversation,
    setSelectedConversation,
  ] = useState(null);


  // =========================
  // MESSAGES
  // =========================

  const [
    messages,
    setMessages,
  ] = useState([]);

  const [
    loadingMessages,
    setLoadingMessages,
  ] = useState(false);

  const [
    messageError,
    setMessageError,
  ] = useState("");

  // =========================
  // MESSAGE PAGINATION
  // =========================

  const [nextMessageCursor, setNextMessageCursor] =
    useState(null);

  const [loadingOlderMessages, setLoadingOlderMessages] =
    useState(false);

  const [hasMoreMessages, setHasMoreMessages] =
    useState(true);

  const messagesContainerRef = useRef(null);

  // =========================
  // MESSAGE SEARCH
  // =========================

  const [messageSearch, setMessageSearch] = useState("");
  const [messageSearchResults, setMessageSearchResults] = useState([]);
  const [messageSearchLoading, setMessageSearchLoading] = useState(false);
  const [messageSearchError, setMessageSearchError] = useState("");
  const [showMessageSearch, setShowMessageSearch] = useState(false);


  // =========================
  // MESSAGE INPUT
  // =========================

  const [
    messageText,
    setMessageText,
  ] = useState("");

  const [
    sendingMessage,
    setSendingMessage,
  ] = useState(false);

  useEffect(() => {

    return () => {

        if (websocketRef.current) {

        websocketRef.current.close();

        websocketRef.current = null;

        }

    };

    }, []);

  // =========================
  // LOAD CONVERSATIONS
  // =========================

  useEffect(() => {

    loadConversations();

  }, []);

  useEffect(() => {

    if (!selectedConversation) {
      return;
    }
    if (!socketConnected) {
      return;
    }

    if (!messages.length) {
      return;
    }

    const receivedMessages =
      messages.filter(
        (message) =>
          String(message.sender?.id) !==
          String(user?.id)
      );

    if (!receivedMessages.length) {
      return;
    }

    const latestReceivedMessage = receivedMessages.reduce(
      (latest, current) => {
        if (!latest) return current;

        return new Date(current.created_at) >
          new Date(latest.created_at)
          ? current
          : latest;
      },
      null
    );

    if (!latestReceivedMessage) return;

    if (
      lastReadMessageRef.current ===
      String(latestReceivedMessage.id)
    ) {
      return;
    }

    sendReadReceipt(latestReceivedMessage.id);

    lastReadMessageRef.current =
      String(latestReceivedMessage.id);

  }, [
    selectedConversation,
    messages,
    user,
    socketConnected,
  ]);

  const handleWebSocketMessage = (data) => {

    // =========================
    // TYPING EVENT
    // =========================

    if (data.type === "typing" && data.data) {

      const userId = String(data.data.user_id);

      // Ignore our own typing event
      if (userId === String(user?.id)) {
        return;
      }

      if (data.data.is_typing) {

        setTypingUserId(userId);

        // Clear previous safety timeout
        if (typingTimeoutRef.current) {
          clearTimeout(typingTimeoutRef.current);
        }

        // Safety timeout
        typingTimeoutRef.current = setTimeout(() => {
          setTypingUserId(null);
          typingTimeoutRef.current = null;
        }, 6000);

      } else {

        setTypingUserId(null);

        if (typingTimeoutRef.current) {
          clearTimeout(typingTimeoutRef.current);
          typingTimeoutRef.current = null;
        }
      }

      return;
    }

    // ==========================================
    // MESSAGE STATUS / READ RECEIPT
    // ==========================================

    if (data.type === "message_status" && data.data) {

      const messageId = String(data.data.message_id);

      const overallStatus =
        data.data.overall_status || data.data.status;

      console.log(
        "Message status received:",
        messageId,
        overallStatus
      );

      setMessages((previousMessages) =>
        previousMessages.map((message) => {

          if (String(message.id) !== messageId) {
            return message;
          }

          return {
            ...message,
            status: overallStatus,
          };
        })
      );

      return;
    }


    // =========================
    // MESSAGE EVENT
    // =========================

    let incomingMessage = null;


    // Standard format
    if (
      data.type === "message" &&
      data.data
    ) {

      incomingMessage = data.data;
    }


    // Alternative format
    else if (
      data.type === "message" &&
      data.message
    ) {

      incomingMessage = data.message;
    }


    // Direct message
    else if (
      data.id &&
      data.content
    ) {

      incomingMessage = data;
    }


    // No message found
    if (!incomingMessage) {

      console.log(
        "WebSocket event:",
        data
      );

      return;
    }


    // =========================
    // STOP TYPING
    // =========================

    setTypingUserId(null);

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = null;
    }


    // =========================
    // PREVENT DUPLICATE
    // =========================

    setMessages(
      (previousMessages) => {

        const alreadyExists =
          previousMessages.some(
            (message) =>
              String(message.id) ===
              String(incomingMessage.id)
          );

        if (alreadyExists) {
          return previousMessages;
        }

        return [
          ...previousMessages,
          incomingMessage,
        ];
      }
    );


    // =========================
    // UPDATE CONVERSATION PREVIEW
    // =========================

    setConversations(
      (previousConversations) =>
        previousConversations.map(
          (conversation) => {

            if (
              String(conversation.id) !==
              String(incomingMessage.conversation_id)
            ) {
              return conversation;
            }

            return {
              ...conversation,

              last_message: {
                id: incomingMessage.id,

                content:
                  incomingMessage.content,

                message_type:
                  incomingMessage.message_type,

                sender_id:
                  incomingMessage.sender?.id ||
                  incomingMessage.sender_id,

                created_at:
                  incomingMessage.created_at,
              },

              updated_at:
                incomingMessage.created_at,
            };
          }
        )
    );
  };


  const connectWebSocket = (conversationId) => {

    // Close previous socket
    if (websocketRef.current) {

        websocketRef.current.close();

        websocketRef.current = null;
    }


    const accessToken =
        localStorage.getItem("access_token");


    if (!accessToken) {

        console.error(
        "Access token not found."
        );

        return;
    }


    const websocketUrl =
        `wss://whatsapp-veus.onrender.com/ws/chat/${conversationId}/?token=${encodeURIComponent(
        accessToken
        )}`;


    console.log(
        "Connecting WebSocket:",
        websocketUrl.replace(
        accessToken,
        "ACCESS_TOKEN"
        )
    );


    const socket =
        new WebSocket(websocketUrl);


    websocketRef.current = socket;


    // =========================
    // SOCKET OPEN
    // =========================

    socket.onopen = () => {

        console.log(
        "WebSocket connected."
        );

        setSocketConnected(true);

    };


    // =========================
    // SOCKET MESSAGE
    // =========================

    socket.onmessage = (event) => {

        try {

        const data =
            JSON.parse(event.data);


        console.log(
            "WebSocket message:",
            data
        );


        handleWebSocketMessage(data);

        } catch (error) {

        console.error(
            "Invalid WebSocket message:",
            event.data
        );

        }

    };


    // =========================
    // SOCKET ERROR
    // =========================

    socket.onerror = (error) => {

        console.error(
        "WebSocket error:",
        error
        );

        setSocketConnected(false);

    };


    // =========================
    // SOCKET CLOSE
    // =========================

    socket.onclose = (event) => {

        console.log(
        "WebSocket disconnected:",
        event.code,
        event.reason
        );

        setSocketConnected(false);

    };

    };

  const connectPresenceWebSocket = () => {
    const accessToken = localStorage.getItem("access_token");

    if (!accessToken) {
      console.error("Access token not found for presence.");
      return;
    }

    // Close previous presence socket
    if (presenceWebsocketRef.current) {
      presenceWebsocketRef.current.close();
      presenceWebsocketRef.current = null;
    }

    const presenceUrl =
      `ws://127.0.0.1:8000/ws/presence/?token=${encodeURIComponent(
        accessToken
      )}`;

    console.log(
      "Connecting Presence WebSocket:",
      presenceUrl.replace(accessToken, "ACCESS_TOKEN")
    );

    const socket = new WebSocket(presenceUrl);

    presenceWebsocketRef.current = socket;

    socket.onopen = () => {
      console.log("Presence WebSocket connected.");

      setPresenceConnected(true);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        console.log("Presence WebSocket message:", data);

        // =========================
        // PRESENCE EVENT
        // =========================

        if (data.type === "presence" && data.data) {
          const userId = String(data.data.user_id);

          const isOnline =
            data.data.status === "online";

          // Update selected user's online status
          setOtherUserOnline(isOnline);

          // Update conversation member data
          setConversations((previousConversations) =>
            previousConversations.map((conversation) => ({
              ...conversation,

              members: conversation.members?.map((member) => {
                if (
                  String(member.user?.id) === userId
                ) {
                  return {
                    ...member,
                    user: {
                      ...member.user,
                      is_online: isOnline,
                      last_seen: data.data.last_seen,
                    },
                  };
                }

                return member;
              }),
            }))
          );

          return;
        }

        // =========================
        // TYPING EVENT
        // =========================

        // if (data.type === "typing" && data.data) {
        //   const userId = String(data.data.user_id);

        //   if (data.data.is_typing) {
        //     setTypingUserId(userId);

        //     // Safety timeout
        //     if (typingTimeoutRef.current) {
        //       clearTimeout(typingTimeoutRef.current);
        //     }

        //     typingTimeoutRef.current = setTimeout(() => {
        //       setTypingUserId(null);
        //     }, 6000);
        //   } else {
        //     setTypingUserId(null);

        //     if (typingTimeoutRef.current) {
        //       clearTimeout(typingTimeoutRef.current);
        //       typingTimeoutRef.current = null;
        //     }
        //   }

        //   return;
        // }

            // ==========================================
            // CONVERSATION UPDATE / UNREAD COUNT
            // ==========================================

            if (data.type === "conversation_update" && data.data) {
              const update  = data.data;

              const conversationId = String(
                update.conversation_id
              );

              console.log(
                "Conversation update received:",
                update
              );

              setConversations((previousConversations) =>
                previousConversations.map((conversation) => {
                  if (String(conversation.id) !== conversationId) {
                    return conversation;
                  }

                  return {
                    ...conversation,

                    // Update unread count
                    unread_count:
                      update.unread_count ??
                      conversation.unread_count ??
                      0,

                    // Update read position
                    last_read_at:
                      update.last_read_at ??
                      conversation.last_read_at,

                    // Keep latest preview if backend provides it
                    last_message:
                      update.last_message ??
                      conversation.last_message,

                    updated_at:
                      update.updated_at ??
                      conversation.updated_at,

                    members:
                      update.members ??
                      conversation.members,
                  };
                })
              );

              return;
            }

      } catch (error) {
        console.error(
          "Invalid presence WebSocket message:",
          event.data,
          error
        );
      }
    };

    socket.onerror = (error) => {
      console.error(
        "Presence WebSocket error:",
        error
      );

      setPresenceConnected(false);
    };

    socket.onclose = (event) => {
      console.log(
        "Presence WebSocket disconnected:",
        event.code,
        event.reason
      );

      setPresenceConnected(false);
    };
  };


  useEffect(() => {
    if (!user) {
      return;
    }

    connectPresenceWebSocket();

    return () => {
      if (presenceWebsocketRef.current) {
        presenceWebsocketRef.current.close();
        presenceWebsocketRef.current = null;
      }

      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
        typingTimeoutRef.current = null;
      }
    };
  }, [user]);

  useEffect(() => {
  if (
    !loadingMessages &&
    messages.length > 0 &&
    selectedConversation
  ) {
    const container =
      messagesContainerRef.current;

    if (!container) {
      return;
    }

    container.scrollTop =
      container.scrollHeight;
  }
}, [
  selectedConversation,
  loadingMessages,
]);

  const loadConversations = async () => {

    try {

      setLoadingConversations(true);
      setConversationError("");

      const response =
        await getConversations();


      console.log(
        "Conversations API response:",
        response
      );


      if (Array.isArray(response)) {

        setConversations(response);

      } else if (
        Array.isArray(response?.data)
      ) {

        setConversations(
          response.data
        );

      } else if (
        Array.isArray(response?.results)
      ) {

        setConversations(
          response.results
        );

      } else {

        console.error(
          "Invalid conversations response:",
          response
        );

        setConversations([]);

        setConversationError(
          "Invalid conversations response from server."
        );
      }

    } catch (error) {

      console.error(
        "Failed to load conversations:",
        error
      );

      setConversationError(
        "Unable to load conversations."
      );

    } finally {

      setLoadingConversations(false);

    }
  };


  // =========================
  // GET OTHER USER
  // =========================

  const getOtherUser = (
    conversation
  ) => {

    if (
      conversation.conversation_type ===
      "group"
    ) {

      return null;
    }


    const member =
      conversation.members?.find(
        (member) =>
          String(member.user.id) !==
          String(user?.id)
      );


    return member?.user || null;
  };


  // =========================
  // GET CONVERSATION NAME
  // =========================

  const getConversationName = (
    conversation
  ) => {

    if (
      conversation.conversation_type ===
      "group"
    ) {

      return (
        conversation.name ||
        "Group"
      );
    }


    const otherUser =
      getOtherUser(conversation);


    return (
      otherUser?.username ||
      otherUser?.email ||
      "Unknown User"
    );
  };


  // =========================
  // GET LAST MESSAGE
  // =========================

  const getLastMessage = (
    conversation
  ) => {

    if (!conversation.last_message) {

      return "No messages yet";

    }


    return (
      conversation.last_message.content ||
      "No messages yet"
    );
  };

  // =========================
  // SEARCH MESSAGES
  // =========================

  const searchMessages = async (searchText) => {
    const query = searchText.trim();

    if (!selectedConversation) {
      return;
    }

    if (!query) {
      setMessageSearchResults([]);
      setMessageSearchError("");
      return;
    }

    try {
      setMessageSearchLoading(true);
      setMessageSearchError("");

      const accessToken =
        localStorage.getItem("access_token");

      if (!accessToken) {
        setMessageSearchError("Access token not found.");
        return;
      }

      const url =
        `http://127.0.0.1:8000/api/v1/chats/conversations/` +
        `${selectedConversation.id}/messages/search/?q=${encodeURIComponent(query)}`;

      console.log("Searching messages:", query);

      const response = await fetch(url, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(
          `Search failed with status ${response.status}`
        );
      }

      const data = await response.json();

      console.log("Message search response:", data);

      let results = [];

      if (Array.isArray(data)) {
        results = data;
      } else if (Array.isArray(data?.data)) {
        results = data.data;
      } else if (Array.isArray(data?.results)) {
        results = data.results;
      }

      setMessageSearchResults(results);

    } catch (error) {
      console.error(
        "Message search failed:",
        error
      );

      setMessageSearchResults([]);
      setMessageSearchError(
        "Unable to search messages."
      );

    } finally {
      setMessageSearchLoading(false);
    }
  };

  const handleMessageSearchChange = (event) => {
    const value = event.target.value;

    setMessageSearch(value);

    searchMessages(value);
  };

  const handleSearchResultClick = (message) => {
    const messageElement = document.getElementById(
      `message-${message.id}`
    );

    if (messageElement) {
      messageElement.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }

    setShowMessageSearch(false);
  };

  // =========================
  // LOAD OLDER MESSAGES
  // =========================

  const loadOlderMessages = async () => {
    if (
      !selectedConversation ||
      !nextMessageCursor ||
      loadingOlderMessages ||
      !hasMoreMessages
    ) {
      return;
    }

    const container =
      messagesContainerRef.current;

    if (!container) {
      return;
    }

    try {
      setLoadingOlderMessages(true);

      // Save current scroll position
      const previousScrollHeight =
        container.scrollHeight;

      const previousScrollTop =
        container.scrollTop;

      const response =
        await getMessages(
          selectedConversation.id,
          nextMessageCursor
        );

      let olderMessages = [];

      if (Array.isArray(response)) {
        olderMessages = response;
      } else if (
        Array.isArray(response?.data)
      ) {
        olderMessages = response.data;
      } else if (
        Array.isArray(response?.results)
      ) {
        olderMessages = response.results;
      }

      // Add older messages before existing messages
      setMessages((previousMessages) => {
        const existingIds = new Set(
          previousMessages.map(
            (message) => String(message.id)
          )
        );

        const uniqueOlderMessages =
          olderMessages.filter(
            (message) =>
              !existingIds.has(
                String(message.id)
              )
          );

        return [
          ...uniqueOlderMessages,
          ...previousMessages,
        ];
      });

      // Update cursor
      setNextMessageCursor(
        response?.next || null
      );

      setHasMoreMessages(
        Boolean(response?.next)
      );

      // Restore scroll position after DOM update
      requestAnimationFrame(() => {
        const newScrollHeight =
          container.scrollHeight;

        container.scrollTop =
          previousScrollTop +
          (newScrollHeight -
            previousScrollHeight);
      });

    } catch (error) {
      console.error(
        "Failed to load older messages:",
        error
      );

      setMessageError(
        "Unable to load older messages."
      );

    } finally {
      setLoadingOlderMessages(false);
    }
  };

  // =========================
  // MESSAGE SCROLL
  // =========================

  const handleMessagesScroll = () => {
    const container =
      messagesContainerRef.current;

    if (!container) {
      return;
    }

    // Near the top
    if (
      container.scrollTop <= 100 &&
      hasMoreMessages &&
      !loadingOlderMessages
    ) {
      loadOlderMessages();
    }
  };
    
      // =========================
  // OPEN CONVERSATION
  // =========================

  const handleConversationClick =
    async (conversation) => {

      setSelectedConversation(conversation);
      setShowMessageSearch(false);
      setMessageSearch("");
      setMessageSearchResults([]);
      setMessageSearchError("");

      // Immediately clear local unread badge
      setConversations((previousConversations) =>
        previousConversations.map((item) => {

          if (
            String(item.id) !==
            String(conversation.id)
          ) {
            return item;
          }

          return {
            ...item,
            unread_count: 0,
          };
        })
      );

      lastReadMessageRef.current = null;
      
      const otherUser = getOtherUser(conversation);

      setOtherUserOnline(
        otherUser?.is_online || false
      );

      setTypingUserId(null);

      setMessages([]);

      setMessageError("");

      setMessageText("");

      setNextMessageCursor(null);
      setHasMoreMessages(true);
      setLoadingOlderMessages(false);

      setLoadingMessages(true);


      try {

        const response =
          await getMessages(
            conversation.id,null
          );


        console.log(
          "Messages API response:",
          response
        );
        let loadedMessages = [];


        if (Array.isArray(response)) {

          loadedMessages = response;

        } else if (
          Array.isArray(response?.data)
        ) {

          loadedMessages = response.data;

        } else if (
          Array.isArray(response?.results)
        ) {

          loadedMessages = response.results;

        } else {

          console.error(
            "Invalid messages response:",
            response
          );

          setMessages([]);

          setMessageError(
            "Invalid messages response from server."
          );
          return;
        }

        // =========================
        // SET MESSAGES
        // =========================

        setMessages(loadedMessages);

        setNextMessageCursor(
          response?.next || null
        );

        setHasMoreMessages(
          Boolean(response?.next)
        );

        // Connect WebSocket
        connectWebSocket(
            conversation.id
        );

      } catch (error) {

        console.error(
          "Failed to load messages:",
          error
        );

        setMessageError(
          "Unable to load messages."
        );

      } finally {

        setLoadingMessages(false);

      }
    };


    const sendTypingStatus = (isTyping) => {
      const socket = websocketRef.current;

      if (
        !socket ||
        socket.readyState !== WebSocket.OPEN
      ) {
        return;
      }

      try {
        socket.send(
          JSON.stringify({
            action: "typing",
            is_typing: isTyping,
          })
        );

        console.log(
          "Typing status sent:",
          isTyping
        );
      } catch (error) {
        console.error(
          "Failed to send typing status:",
          error
        );
      }
    };

  const sendReadReceipt = (messageId) => {

    const socket =
      websocketRef.current;

    if (
      !socket ||
      socket.readyState !== WebSocket.OPEN
    ) {
      return;
    }

    try {

      socket.send(
        JSON.stringify({
          action: "read",
          message_id: messageId,
        })
      );

      console.log(
        "Read receipt sent:",
        messageId
      );

    } catch (error) {

      console.error(
        "Failed to send read receipt:",
        error
      );

    }
  };

  // =========================
  // SEND MESSAGE
  // =========================
  const handleSendMessage = () => {
    const content = messageText.trim();

    if (!content) {
      return;
    }

    if (!selectedConversation) {
      setMessageError("Please select a conversation.");
      return;
    }

    const socket = websocketRef.current;

    console.log("========== SEND MESSAGE ==========");
    console.log("Conversation:", selectedConversation.id);
    console.log("Message:", content);
    console.log("Socket:", socket);

    if (!socket) {
      setMessageError("WebSocket is not connected.");
      console.error("WebSocket reference is null.");
      return;
    }

    if (socket.readyState !== WebSocket.OPEN) {
      setMessageError("Chat connection is not ready.");
      console.error(
        "WebSocket is not OPEN. Ready state:",
        socket.readyState
      );
      return;
    }

    try {
      setSendingMessage(true);
      setMessageError("");

      // =========================
      // STOP TYPING
      // =========================

      if (typingSentRef.current) {
        sendTypingStatus(false);
        typingSentRef.current = false;
      }

      // =========================
      // SEND MESSAGE
      // =========================

      const payload = {
        action: "message",
        message: content,
      };

      console.log("Sending WebSocket payload:", payload);

      socket.send(JSON.stringify(payload));

      console.log("Message sent through WebSocket.");

      setMessageText("");
    } catch (error) {
      console.error(
        "Failed to send WebSocket message:",
        error
      );

      setMessageError("Failed to send message.");
    } finally {
      setSendingMessage(false);
    }
  };


  const handleMessageInputChange = (event) => {
    const value = event.target.value;

    setMessageText(value);

    // No text → stop typing
    if (!value.trim()) {
      if (typingSentRef.current) {
        sendTypingStatus(false);
        typingSentRef.current = false;
      }

      return;
    }

    // Send "typing: true" only once
    if (!typingSentRef.current) {
      sendTypingStatus(true);
      typingSentRef.current = true;
    }
  };

  // =========================
  // ENTER KEY
  // =========================

  const handleMessageKeyDown = (
    event
  ) => {

    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {

      event.preventDefault();

      handleSendMessage();

    }

  };


  // =========================
  // CLOSE CONVERSATION
  // =========================

  const closeConversation = () => {

    if (websocketRef.current) {

        websocketRef.current.close();

        websocketRef.current = null;

    }
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = null;
    }

    typingSentRef.current = false;

    lastReadMessageRef.current = null;

    setTypingUserId(null);


    setSocketConnected(false);

    setSelectedConversation(null);

    setMessages([]);

    setMessageText("");

    setMessageError("");
    setShowMessageSearch(false);
    setMessageSearch("");
    setMessageSearchResults([]);
    setMessageSearchError("");

    };


  // =========================
  // FILTER CONVERSATIONS
  // =========================

  const filteredConversations =
    conversations.filter(
      (conversation) => {

        const name =
          getConversationName(
            conversation
          ).toLowerCase();

        return name.includes(
          search.toLowerCase()
        );

      }
    );


  // =========================
  // SELECTED USER
  // =========================

  const selectedUser =
    selectedConversation
      ? getOtherUser(
          selectedConversation
        )
      : null;


  return (

    <div className="chat-page">


      {/* =================================
          SIDEBAR
      ================================= */}

      <aside
        className={`chat-sidebar ${
          selectedConversation
            ? "mobile-hidden"
            : ""
        }`}
      >


        {/* Header */}

        <div className="sidebar-header">

          <div>

            <h2>
              Chats
            </h2>

            <span>
              {user?.username}
            </span>

          </div>


          <button
            onClick={logout}
            title="Logout"
          >

            <LogOut size={20} />

          </button>

        </div>


        {/* Search */}

        <div className="search-box">

          <Search size={18} />

          <input
            type="text"
            placeholder="Search conversations"
            value={search}
            onChange={(event) =>
              setSearch(
                event.target.value
              )
            }
          />

        </div>


        {/* Conversation List */}

        <div className="conversation-list">


          {loadingConversations && (

            <div className="chat-message">

              Loading conversations...

            </div>

          )}


          {conversationError && (

            <div className="chat-error">

              {conversationError}

            </div>

          )}


          {!loadingConversations &&
            !conversationError &&
            filteredConversations.length ===
              0 && (

              <div className="empty-chat">

                <MessageCircle
                  size={40}
                />

                <p>
                  No conversations found
                </p>

              </div>

            )}


          {!loadingConversations &&
            filteredConversations.map(
              (conversation) => {

                const conversationName =
                  getConversationName(
                    conversation
                  );


                const isSelected =
                  selectedConversation?.id ===
                  conversation.id;


                return (

                  <div
                    key={conversation.id}
                    className={`conversation-item ${
                      isSelected
                        ? "selected"
                        : ""
                    }`}
                    onClick={() =>
                      handleConversationClick(
                        conversation
                      )
                    }
                  >


                    <div className="avatar">

                      {conversationName
                        .charAt(0)
                        .toUpperCase()}

                    </div>


                    <div className="conversation-info">

                      <div className="conversation-top">

                        <strong>
                          {conversationName}
                        </strong>


                        {conversation.last_message && (

                          <span>

                            {new Date(
                              conversation
                                .last_message
                                .created_at
                            ).toLocaleTimeString(
                              [],
                              {
                                hour: "2-digit",
                                minute: "2-digit",
                              }
                            )}

                          </span>

                        )}

                      </div>


                      <div className="conversation-bottom">

                        <span>

                          {getLastMessage(
                            conversation
                          )}

                        </span>


                        {conversation.unread_count >
                          0 && (

                          <span className="unread-count">

                            {
                              conversation.unread_count
                            }

                          </span>

                        )}

                      </div>

                    </div>

                  </div>

                );

              }
            )}

        </div>

      </aside>


      {/* =================================
          CHAT WINDOW
      ================================= */}

      <main
        className={`chat-main ${
          selectedConversation
            ? "chat-open"
            : ""
        }`}
      >


        {!selectedConversation ? (

          <div className="empty-chat-main">

            <MessageCircle
              size={64}
            />

            <h2>
              WhatsApp Clone
            </h2>

            <p>
              Select a conversation to
              start chatting.
            </p>

          </div>

        ) : (

          <div className="chat-window">


            {/* =========================
                CHAT HEADER
            ========================= */}

            <div className="chat-header">

              <button
                className="back-button"
                onClick={
                  closeConversation
                }
              >

                <ArrowLeft size={22} />

              </button>


              <div className="avatar">

                {getConversationName(
                  selectedConversation
                )
                  .charAt(0)
                  .toUpperCase()}

              </div>


              <div className="chat-header-info">

                <strong>

                  {getConversationName(
                    selectedConversation
                  )}

                </strong>


                {selectedConversation
                    .conversation_type ===
                    "one_to_one" &&
                    selectedUser && (

                    <span>
                      {typingUserId &&
                      String(typingUserId) !==
                        String(user?.id)
                        ? "typing..."
                        : otherUserOnline
                          ? "online"
                          : "offline"}

                      {" • "}

                      {socketConnected
                        ? "connected"
                        : "connecting..."}
                    </span>

                    )}

              </div>
              <button
                className="chat-search-button"
                onClick={() => {
                  setShowMessageSearch(
                    (previous) => !previous
                  );

                  setMessageSearch("");
                  setMessageSearchResults([]);
                  setMessageSearchError("");
                }}
                title="Search messages"
              >
                <Search size={20} />
              </button>

            </div>


            {/* =========================
                MESSAGES
            ========================= */}

            {showMessageSearch && (
              <div className="message-search-panel">

                <div className="message-search-input">

                  <Search size={18} />

                  <input
                    type="text"
                    placeholder="Search messages..."
                    value={messageSearch}
                    onChange={
                      handleMessageSearchChange
                    }
                    autoFocus
                  />

                  {messageSearch && (
                    <button
                      onClick={() => {
                        setMessageSearch("");
                        setMessageSearchResults([]);
                        setMessageSearchError("");
                      }}
                    >
                      ×
                    </button>
                  )}

                </div>

                {/* Loading */}

                {messageSearchLoading && (
                  <div className="message-search-status">
                    Searching...
                  </div>
                )}

                {/* Error */}

                {messageSearchError && (
                  <div className="message-search-error">
                    {messageSearchError}
                  </div>
                )}

                {/* Empty */}

                {!messageSearchLoading &&
                  messageSearch.trim() &&
                  !messageSearchError &&
                  messageSearchResults.length === 0 && (
                    <div className="message-search-status">
                      No messages found.
                    </div>
                  )}

                {/* Results */}

                {messageSearchResults.length > 0 && (
                  <div className="message-search-results">

                    {messageSearchResults.map(
                      (message) => (
                        <div
                          key={message.id}
                          className="message-search-result"
                          onClick={() =>
                            handleSearchResultClick(
                              message
                            )
                          }
                        >

                          <div className="message-search-result-user">

                            {message.sender?.username ||
                              message.sender?.email ||
                              "User"}

                          </div>

                          <div className="message-search-result-content">

                            {message.content}

                          </div>

                          <div className="message-search-result-time">

                            {message.created_at &&
                              new Date(
                                message.created_at
                              ).toLocaleString(
                                [],
                                {
                                  dateStyle: "short",
                                  timeStyle: "short",
                                }
                              )}

                          </div>

                        </div>
                      )
                    )}

                  </div>
                )}

              </div>
            )}

            <div
              className="messages-container"
              ref={messagesContainerRef}
              onScroll={handleMessagesScroll}
            >


              {loadingMessages && (

                <div className="chat-message">

                  Loading messages...

                </div>

              )}


              {messageError && (

                <div className="chat-error">

                  {messageError}

                </div>

              )}


              {!loadingMessages &&
                !messageError &&
                messages.length === 0 && (

                <div className="empty-messages">

                  <MessageCircle
                    size={45}
                  />

                  <p>
                    No messages yet
                  </p>

                </div>

              )}


              {!loadingMessages &&
                messages.map(
                  (message) => {

                    const isOwnMessage =
                      String(
                        message.sender?.id
                      ) ===
                      String(user?.id);


                    return (

                      <div
                        id={`message-${message.id}`}
                        key={message.id}
                        className={`message-row ${
                          isOwnMessage
                            ? "own-message"
                            : "other-message"
                        }`}
                      >

                        <div className="message-bubble">

                          <div className="message-content">

                            {message.content}

                          </div>


                          <div className="message-meta">

                            <span>

                              {new Date(
                                message.created_at
                              ).toLocaleTimeString(
                                [],
                                {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                }
                              )}

                            </span>


                            {isOwnMessage && (

                              <span
                                className={`message-status ${
                                  message.status
                                }`}
                              >

                                {message.status ===
                                  "read"
                                  ? "✓✓"
                                  : message.status ===
                                    "delivered"
                                  ? "✓✓"
                                  : "✓"}

                              </span>

                            )}

                          </div>

                        </div>

                      </div>

                    );

                  }
                )}

            </div>


            {/* =========================
                MESSAGE INPUT
            ========================= */}

            <div className="message-input-area">

              <input
                type="text"
                placeholder="Type a message..."
                value={messageText}
                onChange={handleMessageInputChange}
                onKeyDown={
                  handleMessageKeyDown
                }
                disabled={sendingMessage}
              />


              <button
                onClick={
                  handleSendMessage
                }
                disabled={
                  sendingMessage ||
                  !messageText.trim()
                }
                title="Send message"
              >

                {sendingMessage ? (
                  "..."
                ) : (
                  <Send size={18} />
                )}

              </button>

            </div>

          </div>

        )}

      </main>

    </div>

  );
}
export default Chat;