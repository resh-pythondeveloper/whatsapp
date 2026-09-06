import { useEffect, useRef, useState } from "react";

import {
  Search,
  LogOut,
  MessageCircle,
  ArrowLeft,
  Send,
  Plus,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";

import {
  getConversations,
  getMessages,
  searchUsers,
  createOneToOneConversation,
} from "../services/conversationService";

import api from "../services/api";


function Chat() {
  const { user, logout } = useAuth();

  // =========================================================
  // WEBSOCKET
  // =========================================================

  const websocketRef = useRef(null);
  const [socketConnected, setSocketConnected] = useState(false);

  // =========================================================
  // PRESENCE WEBSOCKET
  // =========================================================

  const presenceWebsocketRef = useRef(null);
  const [presenceConnected, setPresenceConnected] = useState(false);
  const [otherUserOnline, setOtherUserOnline] = useState(false);

  // =========================================================
  // TYPING
  // =========================================================

  const typingSentRef = useRef(false);
  const typingTimeoutRef = useRef(null);
  const lastReadMessageRef = useRef(null);

  const [typingUserId, setTypingUserId] = useState(null);

  // =========================================================
  // CONVERSATIONS
  // =========================================================

  const [conversations, setConversations] = useState([]);
  const [loadingConversations, setLoadingConversations] =
    useState(true);
  const [conversationError, setConversationError] =
    useState("");

  const [search, setSearch] = useState("");

  // =========================================================
  // USER SEARCH
  // =========================================================

  const [userSearch, setUserSearch] = useState("");

  const [userSearchResults, setUserSearchResults] =
    useState([]);

  const [userSearchLoading, setUserSearchLoading] =
    useState(false);

  const [showStartConversation, setShowStartConversation] =
    useState(false);

  const userSearchRequestRef = useRef(0);

  // =========================================================
  // SELECTED CONVERSATION
  // =========================================================

  const [selectedConversation, setSelectedConversation] =
    useState(null);

  // =========================================================
  // MESSAGES
  // =========================================================

  const [messages, setMessages] = useState([]);
  const [loadingMessages, setLoadingMessages] =
    useState(false);
  const [messageError, setMessageError] = useState("");

  // =========================================================
  // MESSAGE PAGINATION
  // =========================================================

  const [nextMessageCursor, setNextMessageCursor] =
    useState(null);

  const [loadingOlderMessages, setLoadingOlderMessages] =
    useState(false);

  const [hasMoreMessages, setHasMoreMessages] =
    useState(true);

  const messagesContainerRef = useRef(null);

  const pendingScrollRestoreRef = useRef(null);

  // =========================================================
  // MESSAGE SEARCH
  // =========================================================

  const [messageSearch, setMessageSearch] = useState("");
  const [messageSearchResults, setMessageSearchResults] =
    useState([]);
  const [messageSearchLoading, setMessageSearchLoading] =
    useState(false);
  const [messageSearchError, setMessageSearchError] =
    useState("");
  const [showMessageSearch, setShowMessageSearch] =
    useState(false);

  // =========================================================
  // MESSAGE INPUT
  // =========================================================

  const [messageText, setMessageText] = useState("");
  const [sendingMessage, setSendingMessage] =
    useState(false);

  // =========================================================
  // API / WEBSOCKET URL
  // =========================================================

  /*
   * Local:
   * VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
   * VITE_WS_BASE_URL=ws://127.0.0.1:8000
   *
   * Production:
   * VITE_API_BASE_URL=https://whatsapp-veus.onrender.com/api/v1
   * VITE_WS_BASE_URL=wss://whatsapp-veus.onrender.com
   */

  const WS_BASE_URL =
    import.meta.env.VITE_WS_BASE_URL;

  // =========================================================
  // EXTRACT CURSOR FROM DRF NEXT URL
  // =========================================================

  const getCursorFromUrl = (url) => {
    if (!url) {
      return null;
    }

    try {
      const parsedUrl = new URL(url);

      return parsedUrl.searchParams.get("cursor");
    } catch (error) {
      console.error(
        "Failed to parse pagination URL:",
        url,
        error
      );

      return null;
    }
  };

  // =========================================================
  // NORMALIZE MESSAGE
  // =========================================================

  const normalizeMessage = (message) => {
    if (!message) {
      return null;
    }

    return {
      ...message,

      sender_id:
        message.sender_id ??
        message.sender?.id ??
        null,

      conversation_id:
        message.conversation_id ??
        message.conversation?.id ??
        null,
    };
  };

  // =========================================================
  // CLEANUP ON COMPONENT UNMOUNT
  // =========================================================

  useEffect(() => {
    return () => {
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }

      if (presenceWebsocketRef.current) {
        presenceWebsocketRef.current.close();
        presenceWebsocketRef.current = null;
      }

      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
        typingTimeoutRef.current = null;
      }
    };
  }, []);

  // =========================================================
  // LOAD CONVERSATIONS
  // =========================================================

  useEffect(() => {
    if (!user) {
      return;
    }

    loadConversations();
  }, [user]);

  // =========================================================
  // KEEP SELECTED USER ONLINE STATUS UPDATED
  // =========================================================

  useEffect(() => {
    if (!selectedConversation) {
      setOtherUserOnline(false);
      return;
    }

    const updatedConversation =
      conversations.find(
        (conversation) =>
          String(conversation.id) ===
          String(selectedConversation.id)
      );

    if (!updatedConversation) {
      return;
    }

    const otherUser =
      getOtherUser(updatedConversation);

    setOtherUserOnline(
      Boolean(otherUser?.is_online)
    );

    setSelectedConversation(
      (previousConversation) => {
        if (!previousConversation) {
          return previousConversation;
        }

        if (
          String(previousConversation.id) !==
          String(updatedConversation.id)
        ) {
          return previousConversation;
        }

        return updatedConversation;
      }
    );
  }, [conversations]);

  // =========================================================
  // AUTO READ LATEST RECEIVED MESSAGE
  // =========================================================

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

    const receivedMessages = messages.filter(
      (message) => {
        const senderId =
          message.sender?.id ??
          message.sender_id;

        return (
          String(senderId) !==
          String(user?.id)
        );
      }
    );

    if (!receivedMessages.length) {
      return;
    }

    const latestReceivedMessage =
      receivedMessages.reduce(
        (latest, current) => {
          if (!latest) {
            return current;
          }

          return new Date(current.created_at) >
            new Date(latest.created_at)
            ? current
            : latest;
        },
        null
      );

    if (!latestReceivedMessage) {
      return;
    }

    if (
      lastReadMessageRef.current ===
      String(latestReceivedMessage.id)
    ) {
      return;
    }

    sendReadReceipt(
      latestReceivedMessage.id
    );

    lastReadMessageRef.current =
      String(latestReceivedMessage.id);

  }, [
    selectedConversation,
    messages,
    user,
    socketConnected,
  ]);

  // =========================================================
  // RESTORE SCROLL POSITION
  // =========================================================

  useEffect(() => {
    if (!pendingScrollRestoreRef.current) {
      return;
    }

    const container =
      messagesContainerRef.current;

    if (!container) {
      return;
    }

    const {
      previousScrollTop,
      previousScrollHeight,
    } = pendingScrollRestoreRef.current;

    const newScrollHeight =
      container.scrollHeight;

    container.scrollTop =
      previousScrollTop +
      (newScrollHeight - previousScrollHeight);

    pendingScrollRestoreRef.current = null;

  }, [messages]);

  // =========================================================
  // INITIAL SCROLL TO BOTTOM
  // =========================================================

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

      if (pendingScrollRestoreRef.current) {
        return;
      }

      container.scrollTop =
        container.scrollHeight;
    }

  }, [
    selectedConversation,
    loadingMessages,
  ]);

  // =========================================================
  // HANDLE WEBSOCKET MESSAGE
  // =========================================================

  const handleWebSocketMessage = (data) => {

    // =======================================================
    // TYPING EVENT
    // =======================================================

    if (
      data.type === "typing" &&
      data.data
    ) {
      const userId =
        String(data.data.user_id);

      if (
        userId === String(user?.id)
      ) {
        return;
      }

      if (data.data.is_typing) {
        setTypingUserId(userId);

        if (typingTimeoutRef.current) {
          clearTimeout(
            typingTimeoutRef.current
          );
        }

        typingTimeoutRef.current =
          setTimeout(() => {
            setTypingUserId(null);
            typingTimeoutRef.current = null;
          }, 6000);

      } else {
        setTypingUserId(null);

        if (typingTimeoutRef.current) {
          clearTimeout(
            typingTimeoutRef.current
          );

          typingTimeoutRef.current = null;
        }
      }

      return;
    }

    // =======================================================
    // MESSAGE STATUS / RECEIPT
    // =======================================================

    if (
      data.type === "message_status" &&
      data.data
    ) {
      const messageId =
        String(data.data.message_id);

      const overallStatus =
        data.data.overall_status ||
        data.data.status;

      console.log(
        "Message status received:",
        messageId,
        overallStatus
      );

      setMessages(
        (previousMessages) =>
          previousMessages.map(
            (message) => {
              if (
                String(message.id) !==
                messageId
              ) {
                return message;
              }

              return {
                ...message,
                status:
                  overallStatus ||
                  message.status,
              };
            }
          )
      );

      return;
    }

    // =======================================================
    // MESSAGE EVENT
    // =======================================================

    let incomingMessage = null;

    if (
      data.type === "message" &&
      data.data
    ) {
      incomingMessage = data.data;
    }

    else if (
      data.type === "message" &&
      data.message
    ) {
      incomingMessage = data.message;
    }

    else if (
      data.id &&
      data.content
    ) {
      incomingMessage = data;
    }

    if (!incomingMessage) {
      console.log(
        "WebSocket event:",
        data
      );

      return;
    }

    // =======================================================
    // NORMALIZE MESSAGE
    // =======================================================

    const normalizedMessage =
      normalizeMessage(
        incomingMessage
      );

    if (!normalizedMessage) {
      return;
    }

    // =======================================================
    // STOP TYPING
    // =======================================================

    setTypingUserId(null);

    if (typingTimeoutRef.current) {
      clearTimeout(
        typingTimeoutRef.current
      );

      typingTimeoutRef.current = null;
    }

    // =======================================================
    // ADD MESSAGE WITHOUT DUPLICATE
    // =======================================================

    setMessages(
      (previousMessages) => {
        const alreadyExists =
          previousMessages.some(
            (message) =>
              String(message.id) ===
              String(normalizedMessage.id)
          );

        if (alreadyExists) {
          return previousMessages;
        }

        return [
          ...previousMessages,
          normalizedMessage,
        ];
      }
    );

    // =======================================================
    // UPDATE CONVERSATION PREVIEW
    // =======================================================

    setConversations(
      (previousConversations) =>
        previousConversations.map(
          (conversation) => {
            if (
              String(conversation.id) !==
              String(
                normalizedMessage.conversation_id
              )
            ) {
              return conversation;
            }

            return {
              ...conversation,

              last_message: {
                id:
                  normalizedMessage.id,

                content:
                  normalizedMessage.content,

                message_type:
                  normalizedMessage.message_type,

                sender_id:
                  normalizedMessage.sender_id,

                created_at:
                  normalizedMessage.created_at,
              },

              updated_at:
                normalizedMessage.created_at,
            };
          }
        )
    );
  };

  // =========================================================
  // CONNECT CHAT WEBSOCKET
  // =========================================================

  const connectWebSocket = (
    conversationId
  ) => {

    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }

    setSocketConnected(false);

    const accessToken =
      localStorage.getItem(
        "access_token"
      );

    if (!accessToken) {
      console.error(
        "Access token not found."
      );

      return;
    }

    if (!WS_BASE_URL) {
      console.error(
        "VITE_WS_BASE_URL is not configured."
      );

      return;
    }

    const websocketUrl =
      `${WS_BASE_URL}/ws/chat/${conversationId}/?token=${encodeURIComponent(
        accessToken
      )}`;

    console.log(
      "Connecting Chat WebSocket:",
      websocketUrl.replace(
        accessToken,
        "ACCESS_TOKEN"
      )
    );

    const socket =
      new WebSocket(websocketUrl);

    websocketRef.current = socket;

    socket.onopen = () => {
      console.log(
        "Chat WebSocket connected."
      );

      if (
        websocketRef.current === socket
      ) {
        setSocketConnected(true);
      }
    };

    socket.onmessage = (event) => {
      try {
        const data =
          JSON.parse(event.data);

        console.log(
          "Chat WebSocket message:",
          data
        );

        handleWebSocketMessage(data);

      } catch (error) {
        console.error(
          "Invalid WebSocket message:",
          event.data,
          error
        );
      }
    };

    socket.onerror = (error) => {
      console.error(
        "Chat WebSocket error:",
        error
      );

      if (
        websocketRef.current === socket
      ) {
        setSocketConnected(false);
      }
    };

    socket.onclose = (event) => {
      console.log(
        "Chat WebSocket disconnected:",
        event.code,
        event.reason
      );

      if (
        websocketRef.current === socket
      ) {
        websocketRef.current = null;
        setSocketConnected(false);
      }
    };
  };

  // =========================================================
  // CONNECT PRESENCE WEBSOCKET
  // =========================================================

  const connectPresenceWebSocket = () => {
    const accessToken =
      localStorage.getItem(
        "access_token"
      );

    if (!accessToken) {
      console.error(
        "Access token not found for presence."
      );

      return;
    }

    if (!WS_BASE_URL) {
      console.error(
        "VITE_WS_BASE_URL is not configured."
      );

      return;
    }

    if (
      presenceWebsocketRef.current
    ) {
      presenceWebsocketRef.current.close();

      presenceWebsocketRef.current = null;
    }

    setPresenceConnected(false);

    const presenceUrl =
      `${WS_BASE_URL}/ws/presence/?token=${encodeURIComponent(
        accessToken
      )}`;

    console.log(
      "Connecting Presence WebSocket:",
      presenceUrl.replace(
        accessToken,
        "ACCESS_TOKEN"
      )
    );

    const socket =
      new WebSocket(presenceUrl);

    presenceWebsocketRef.current =
      socket;

    socket.onopen = () => {
      console.log(
        "Presence WebSocket connected."
      );

      if (
        presenceWebsocketRef.current ===
        socket
      ) {
        setPresenceConnected(true);
      }
    };

    socket.onmessage = (event) => {
      try {
        const data =
          JSON.parse(event.data);

        console.log(
          "Presence WebSocket message:",
          data
        );

        // =====================================================
        // PRESENCE
        // =====================================================

        if (
          data.type === "presence" &&
          data.data
        ) {
          const userId =
            String(data.data.user_id);

          const isOnline =
            data.data.status ===
            "online";

          setConversations(
            (previousConversations) =>
              previousConversations.map(
                (conversation) => ({
                  ...conversation,

                  members:
                    conversation.members?.map(
                      (member) => {
                        if (
                          String(
                            member.user?.id
                          ) === userId
                        ) {
                          return {
                            ...member,

                            user: {
                              ...member.user,

                              is_online:
                                isOnline,

                              last_seen:
                                data.data
                                  .last_seen,
                            },
                          };
                        }

                        return member;
                      }
                    ),
                })
              )
          );

          return;
        }

        // =====================================================
        // CONVERSATION UPDATE
        // =====================================================

        if (
          data.type ===
            "conversation_update" &&
          data.data
        ) {
          const update =
            data.data;

          const conversationId =
            String(
              update.conversation_id
            );

          console.log(
            "Conversation update received:",
            update
          );

          setConversations(
            (previousConversations) =>
              previousConversations.map(
                (conversation) => {
                  if (
                    String(
                      conversation.id
                    ) !==
                    conversationId
                  ) {
                    return conversation;
                  }

                  return {
                    ...conversation,

                    unread_count:
                      update.unread_count ??
                      conversation.unread_count ??
                      0,

                    last_read_at:
                      update.last_read_at ??
                      conversation.last_read_at,

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
                }
              )
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

      if (
        presenceWebsocketRef.current ===
        socket
      ) {
        setPresenceConnected(false);
      }
    };

    socket.onclose = (event) => {
      console.log(
        "Presence WebSocket disconnected:",
        event.code,
        event.reason
      );

      if (
        presenceWebsocketRef.current ===
        socket
      ) {
        presenceWebsocketRef.current = null;
        setPresenceConnected(false);
      }
    };
  };

  // =========================================================
  // PRESENCE EFFECT
  // =========================================================

  useEffect(() => {
    if (!user) {
      return;
    }

    connectPresenceWebSocket();

    return () => {
      if (
        presenceWebsocketRef.current
      ) {
        presenceWebsocketRef.current.close();

        presenceWebsocketRef.current =
          null;
      }

      if (typingTimeoutRef.current) {
        clearTimeout(
          typingTimeoutRef.current
        );

        typingTimeoutRef.current = null;
      }
    };

  }, [user]);

  // =========================================================
  // LOAD CONVERSATIONS
  // =========================================================

  const loadConversations =
    async () => {
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
          setConversations(
            response
          );

        } else if (
          Array.isArray(
            response?.data
          )
        ) {
          setConversations(
            response.data
          );

        } else if (
          Array.isArray(
            response?.results
          )
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

        console.error(
          "Response:",
          error.response?.data
        );

        setConversationError(
          error.response?.data?.detail ||
          "Unable to load conversations."
        );

      } finally {
        setLoadingConversations(
          false
        );
      }
    };

  // =========================================================
  // GET OTHER USER
  // =========================================================

  const getOtherUser = (
    conversation
  ) => {
    if (
      !conversation ||
      conversation.conversation_type ===
        "group"
    ) {
      return null;
    }

    const member =
      conversation.members?.find(
        (member) =>
          String(
            member.user?.id
          ) !==
          String(user?.id)
      );

    return (
      member?.user || null
    );
  };

  // =========================================================
  // GET CONVERSATION NAME
  // =========================================================

  const getConversationName = (
    conversation
  ) => {
    if (!conversation) {
      return "Unknown User";
    }

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
      getOtherUser(
        conversation
      );

    return (
      otherUser?.username ||
      otherUser?.email ||
      "Unknown User"
    );
  };

  // =========================================================
  // GET LAST MESSAGE
  // =========================================================

  const getLastMessage = (
    conversation
  ) => {
    if (
      !conversation?.last_message
    ) {
      return "No messages yet";
    }

    return (
      conversation.last_message
        .content ||
      "No messages yet"
    );
  };

  // =========================================================
  // LOAD UNCHATTED USERS
  // =========================================================

  const loadUnchattedUsers = async (
    query = ""
  ) => {
    const requestId =
      ++userSearchRequestRef.current;

    try {
      setUserSearchLoading(true);

      const response =
        await searchUsers(query);

      if (
        requestId !==
        userSearchRequestRef.current
      ) {
        return;
      }

      console.log(
        "Unchatted users response:",
        response
      );

      if (Array.isArray(response)) {
        setUserSearchResults(response);
      } else {
        setUserSearchResults([]);
      }

    } catch (error) {

      if (
        requestId !==
        userSearchRequestRef.current
      ) {
        return;
      }

      console.error(
        "Failed to load unchatted users:",
        error
      );

      setUserSearchResults([]);

    } finally {

      if (
        requestId ===
        userSearchRequestRef.current
      ) {
        setUserSearchLoading(false);
      }
    }
  };


  // =========================================================
  // SEARCH UNCHATTED USERS
  // =========================================================

  const handleUserSearch =
    async (value) => {

      setUserSearch(value);

      await loadUnchattedUsers(
        value.trim()
      );
    };


  // =========================================================
  // OPEN START CONVERSATION
  // =========================================================

  const openStartConversation =
    async () => {

      setShowStartConversation(true);

      setUserSearch("");

      setUserSearchResults([]);

      setUserSearchLoading(true);

      await loadUnchattedUsers("");
    };


  // =========================================================
  // CLOSE START CONVERSATION
  // =========================================================

  const closeStartConversation =
    () => {

      userSearchRequestRef.current += 1;

      setShowStartConversation(false);

      setUserSearch("");

      setUserSearchResults([]);

      setUserSearchLoading(false);
    };

  // =========================================================
  // CLICK USER SEARCH RESULT
  // =========================================================

  const handleUserClick =
    async (selectedUser) => {
      try {
        setMessageError("");

        console.log(
          "Creating/opening conversation with:",
          selectedUser
        );

        const response =
          await createOneToOneConversation(
            selectedUser.id
          );

        console.log(
          "One-to-one conversation response:",
          response
        );

        const conversation =
          response?.conversation ||
          response?.data ||
          response;

        if (
          !conversation?.id
        ) {
          throw new Error(
            "Invalid conversation response."
          );
        }

        setConversations(
          (previousConversations) => {
            const exists =
              previousConversations.some(
                (item) =>
                  String(item.id) ===
                  String(
                    conversation.id
                  )
              );

            if (exists) {
              return previousConversations.map(
                (item) =>
                  String(item.id) ===
                  String(
                    conversation.id
                  )
                    ? conversation
                    : item
              );
            }

            return [
              conversation,
              ...previousConversations,
            ];
          }
        );

        setUserSearch("");

        setUserSearchResults([]);

        setUserSearchLoading(false);

        setShowStartConversation(false);

        await handleConversationClick(
          conversation
        );

      } catch (error) {
        console.error(
          "Failed to create/open conversation:",
          error
        );

        console.error(
          "Response:",
          error.response?.data
        );

        setMessageError(
          error.response?.data
            ?.detail ||
          error.response?.data
            ?.message ||
          "Unable to open conversation."
        );
      }
    };

  // =========================================================
  // SEARCH MESSAGES
  // =========================================================

  const searchMessages =
    async (searchText) => {
      const query =
        searchText.trim();

      if (!selectedConversation) {
        return;
      }

      if (!query) {
        setMessageSearchResults([]);
        setMessageSearchError("");

        return;
      }

      try {
        setMessageSearchLoading(
          true
        );

        setMessageSearchError("");

        console.log(
          "Searching messages:",
          query
        );

        const response =
          await api.get(
            `/chats/conversations/${selectedConversation.id}/messages/search/`,
            {
              params: {
                q: query,
              },
            }
          );

        console.log(
          "Message search response:",
          response.data
        );

        const data =
          response.data;

        let results = [];

        if (
          Array.isArray(data)
        ) {
          results = data;

        } else if (
          Array.isArray(
            data?.data
          )
        ) {
          results = data.data;

        } else if (
          Array.isArray(
            data?.results
          )
        ) {
          results =
            data.results;
        }

        setMessageSearchResults(
          results
        );

      } catch (error) {
        console.error(
          "Message search failed:",
          error
        );

        console.error(
          "Response:",
          error.response?.data
        );

        setMessageSearchResults([]);

        setMessageSearchError(
          error.response?.data?.detail ||
          "Unable to search messages."
        );

      } finally {
        setMessageSearchLoading(
          false
        );
      }
    };

  // =========================================================
  // MESSAGE SEARCH INPUT
  // =========================================================

  const handleMessageSearchChange =
    (event) => {
      const value =
        event.target.value;

      setMessageSearch(value);

      searchMessages(value);
    };

  // =========================================================
  // CLICK MESSAGE SEARCH RESULT
  // =========================================================

  const handleSearchResultClick =
    (message) => {
      const messageElement =
        document.getElementById(
          `message-${message.id}`
        );

      if (messageElement) {
        messageElement.scrollIntoView(
          {
            behavior: "smooth",
            block: "center",
          }
        );
      } else {
        console.log(
          "Message is not currently loaded:",
          message.id
        );
      }

      setShowMessageSearch(
        false
      );
    };

  // =========================================================
  // LOAD OLDER MESSAGES
  // =========================================================

  const loadOlderMessages =
    async () => {
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
        setLoadingOlderMessages(
          true
        );

        const previousScrollHeight =
          container.scrollHeight;

        const previousScrollTop =
          container.scrollTop;

        pendingScrollRestoreRef.current =
          {
            previousScrollHeight,
            previousScrollTop,
          };

        const response =
          await getMessages(
            selectedConversation.id,
            nextMessageCursor
          );

        console.log(
          "Older messages response:",
          response
        );

        let olderMessages = [];

        if (
          Array.isArray(response)
        ) {
          olderMessages =
            response;

        } else if (
          Array.isArray(
            response?.data
          )
        ) {
          olderMessages =
            response.data;

        } else if (
          Array.isArray(
            response?.results
          )
        ) {
          olderMessages =
            response.results;
        }

        olderMessages =
          olderMessages.map(
            normalizeMessage
          );

        olderMessages =
          [...olderMessages].reverse();

        setMessages(
          (previousMessages) => {
            const existingIds =
              new Set(
                previousMessages.map(
                  (message) =>
                    String(
                      message.id
                    )
                )
              );

            const uniqueOlderMessages =
              olderMessages.filter(
                (message) =>
                  !existingIds.has(
                    String(
                      message.id
                    )
                  )
              );

            return [
              ...uniqueOlderMessages,
              ...previousMessages,
            ];
          }
        );

        const nextCursor =
          getCursorFromUrl(
            response?.next
          );

        console.log(
          "Next message cursor:",
          nextCursor
        );

        setNextMessageCursor(
          nextCursor
        );

        setHasMoreMessages(
          Boolean(nextCursor)
        );

      } catch (error) {
        console.error(
          "Failed to load older messages:",
          error
        );

        pendingScrollRestoreRef.current =
          null;

        setMessageError(
          "Unable to load older messages."
        );

      } finally {
        setLoadingOlderMessages(
          false
        );
      }
    };

  // =========================================================
  // MESSAGE SCROLL
  // =========================================================

  const handleMessagesScroll =
    () => {
      const container =
        messagesContainerRef.current;

      if (!container) {
        return;
      }

      if (
        container.scrollTop <=
          100 &&
        hasMoreMessages &&
        !loadingOlderMessages
      ) {
        loadOlderMessages();
      }
    };

  // =========================================================
  // OPEN CONVERSATION
  // =========================================================

  const handleConversationClick =
    async (conversation) => {

      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }

      setSocketConnected(false);

      setSelectedConversation(
        conversation
      );

      setShowMessageSearch(
        false
      );

      setMessageSearch("");
      setMessageSearchResults([]);
      setMessageSearchError("");

      setConversations(
        (previousConversations) =>
          previousConversations.map(
            (item) => {
              if (
                String(item.id) !==
                String(
                  conversation.id
                )
              ) {
                return item;
              }

              return {
                ...item,
                unread_count: 0,
              };
            }
          )
      );

      lastReadMessageRef.current =
        null;

      const otherUser =
        getOtherUser(
          conversation
        );

      setOtherUserOnline(
        Boolean(
          otherUser?.is_online
        )
      );

      setTypingUserId(null);

      if (typingTimeoutRef.current) {
        clearTimeout(
          typingTimeoutRef.current
        );

        typingTimeoutRef.current =
          null;
      }

      typingSentRef.current =
        false;

      setMessages([]);

      setMessageError("");

      setMessageText("");

      setNextMessageCursor(
        null
      );

      setHasMoreMessages(
        true
      );

      setLoadingOlderMessages(
        false
      );

      pendingScrollRestoreRef.current =
        null;

      setLoadingMessages(
        true
      );

      try {
        const response =
          await getMessages(
            conversation.id,
            null
          );

        console.log(
          "Messages API response:",
          response
        );

        let loadedMessages = [];

        if (
          Array.isArray(response)
        ) {
          loadedMessages =
            response;

        } else if (
          Array.isArray(
            response?.data
          )
        ) {
          loadedMessages =
            response.data;

        } else if (
          Array.isArray(
            response?.results
          )
        ) {
          loadedMessages =
            response.results;

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

        loadedMessages =
          loadedMessages.map(
            normalizeMessage
          );

        const nextCursor =
          getCursorFromUrl(
            response?.next
          );

        console.log(
          "Initial next cursor:",
          nextCursor
        );

        if (
          loadedMessages.length > 1
        ) {
          loadedMessages =
            [...loadedMessages].reverse();
        }

        setMessages(
          loadedMessages
        );

        setNextMessageCursor(
          nextCursor
        );

        setHasMoreMessages(
          Boolean(nextCursor)
        );

        connectWebSocket(
          conversation.id
        );

      } catch (error) {
        console.error(
          "Failed to load messages:",
          error
        );

        console.error(
          "Response:",
          error.response?.data
        );

        setMessageError(
          error.response?.data?.detail ||
          "Unable to load messages."
        );

      } finally {
        setLoadingMessages(
          false
        );
      }
    };

  // =========================================================
  // SEND TYPING STATUS
  // =========================================================

  const sendTypingStatus =
    (isTyping) => {
      const socket =
        websocketRef.current;

      if (
        !socket ||
        socket.readyState !==
          WebSocket.OPEN
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

  // =========================================================
  // SEND READ RECEIPT
  // =========================================================

  const sendReadReceipt =
    (messageId) => {
      const socket =
        websocketRef.current;

      if (
        !socket ||
        socket.readyState !==
          WebSocket.OPEN
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

  // =========================================================
  // SEND MESSAGE
  // =========================================================

  const handleSendMessage =
    () => {
      const content =
        messageText.trim();

      if (!content) {
        return;
      }

      if (!selectedConversation) {
        setMessageError(
          "Please select a conversation."
        );

        return;
      }

      const socket =
        websocketRef.current;

      console.log(
        "========== SEND MESSAGE =========="
      );

      console.log(
        "Conversation:",
        selectedConversation.id
      );

      console.log(
        "Message:",
        content
      );

      if (!socket) {
        setMessageError(
          "WebSocket is not connected."
        );

        return;
      }

      if (
        socket.readyState !==
        WebSocket.OPEN
      ) {
        setMessageError(
          "Chat connection is not ready."
        );

        return;
      }

      try {
        setSendingMessage(
          true
        );

        setMessageError("");

        if (
          typingSentRef.current
        ) {
          sendTypingStatus(
            false
          );

          typingSentRef.current =
            false;
        }

        const payload = {
          action: "message",
          message: content,
        };

        console.log(
          "Sending WebSocket payload:",
          payload
        );

        socket.send(
          JSON.stringify(payload)
        );

        setMessageText("");

      } catch (error) {
        console.error(
          "Failed to send WebSocket message:",
          error
        );

        setMessageError(
          "Failed to send message."
        );

      } finally {
        setSendingMessage(
          false
        );
      }
    };

  // =========================================================
  // MESSAGE INPUT CHANGE
  // =========================================================

  const handleMessageInputChange =
    (event) => {
      const value =
        event.target.value;

      setMessageText(value);

      if (!value.trim()) {
        if (
          typingSentRef.current
        ) {
          sendTypingStatus(
            false
          );

          typingSentRef.current =
            false;
        }

        return;
      }

      if (
        !typingSentRef.current
      ) {
        sendTypingStatus(
          true
        );

        typingSentRef.current =
          true;
      }
    };

  // =========================================================
  // ENTER KEY
  // =========================================================

  const handleMessageKeyDown =
    (event) => {
      if (
        event.key === "Enter" &&
        !event.shiftKey
      ) {
        event.preventDefault();

        handleSendMessage();
      }
    };

  // =========================================================
  // CLOSE CONVERSATION
  // =========================================================

  const closeConversation =
    () => {
      if (websocketRef.current) {
        websocketRef.current.close();

        websocketRef.current =
          null;
      }

      if (
        typingTimeoutRef.current
      ) {
        clearTimeout(
          typingTimeoutRef.current
        );

        typingTimeoutRef.current =
          null;
      }

      typingSentRef.current =
        false;

      lastReadMessageRef.current =
        null;

      pendingScrollRestoreRef.current =
        null;

      setTypingUserId(null);

      setSocketConnected(
        false
      );

      setSelectedConversation(
        null
      );

      setMessages([]);

      setMessageText("");

      setMessageError("");

      setShowMessageSearch(
        false
      );

      setMessageSearch("");

      setMessageSearchResults([]);

      setMessageSearchError("");

      setNextMessageCursor(
        null
      );

      setHasMoreMessages(
        true
      );

      setLoadingOlderMessages(
        false
      );

      setOtherUserOnline(false);
    };

  // =========================================================
  // FILTER CONVERSATIONS
  // =========================================================

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

  // =========================================================
  // SELECTED USER
  // =========================================================

  const selectedUser =
    selectedConversation
      ? getOtherUser(
          selectedConversation
        )
      : null;

  // =========================================================
  // RENDER
  // =========================================================

  return (
    <div className="chat-page">

      {/* =====================================================
          SIDEBAR
      ===================================================== */}

      <aside
        className={`chat-sidebar ${
          selectedConversation
            ? "mobile-hidden"
            : ""
        }`}
      >

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

        {/* =====================================================
            SIDEBAR CONTENT
        ===================================================== */}

        {showStartConversation ? (

          /* =====================================================
            START CONVERSATION SCREEN
          ===================================================== */

          <div className="start-conversation-container">

            {/* HEADER */}

            <div className="start-conversation-header">

              <button
                className="start-conversation-back"
                onClick={
                  closeStartConversation
                }
                title="Back"
              >
                <ArrowLeft size={20} />
              </button>

              <div>
                <h3>
                  Start Conversation
                </h3>

                <span>
                  Select a person to chat
                </span>
              </div>

            </div>


            {/* SEARCH */}

            <div className="search-box">

              <Search size={18} />

              <input
                type="text"
                placeholder="Search people"
                value={userSearch}
                onChange={(event) =>
                  handleUserSearch(
                    event.target.value
                  )
                }
                autoFocus
              />

            </div>


            {/* USER LIST */}

            <div className="conversation-list">

              {userSearchLoading && (
                <div className="search-status">
                  Loading people...
                </div>
              )}


              {!userSearchLoading &&
                userSearchResults.length === 0 && (
                  <div className="empty-chat">

                    <MessageCircle
                      size={40}
                    />

                    <p>
                      {userSearch.trim()
                        ? "No people found"
                        : "No new people available"}
                    </p>

                  </div>
                )}


              {!userSearchLoading &&
                userSearchResults.length > 0 &&
                userSearchResults.map(
                  (searchUser) => {

                    const username =
                      searchUser.username ||
                      "Unknown User";

                    return (
                      <div
                        key={searchUser.id}
                        className="user-search-item"
                        onClick={() =>
                          handleUserClick(
                            searchUser
                          )
                        }
                      >

                        {/* AVATAR */}

                        <div className="avatar">
                          {username
                            .charAt(0)
                            .toUpperCase()}
                        </div>


                        {/* USER INFO */}

                        <div className="user-search-info">

                          <strong>
                            {username}
                          </strong>

                          <span>
                            {searchUser.is_online
                              ? "online"
                              : "offline"}
                          </span>

                        </div>

                      </div>
                    );
                  }
                )}

            </div>

          </div>

        ) : (

          /* =====================================================
            NORMAL CHATS SCREEN
          ===================================================== */

          <>

            {/* START CONVERSATION BUTTON */}

            <button
              className="start-conversation-button"
              onClick={
                openStartConversation
              }
            >

              <Plus size={18} />

              <span>
                Start Conversation
              </span>

            </button>


            {/* CHAT SEARCH */}

            <div className="search-box">

              <Search size={18} />

              <input
                type="text"
                placeholder="Search chats"
                value={search}
                onChange={(event) =>
                  setSearch(
                    event.target.value
                  )
                }
              />

            </div>


            {/* CONVERSATION LIST */}

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
                      String(
                        selectedConversation?.id
                      ) ===
                      String(
                        conversation.id
                      );

                    return (
                      <div
                        key={
                          conversation.id
                        }
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

                        {/* AVATAR */}

                        <div className="avatar">

                          {conversationName
                            .charAt(0)
                            .toUpperCase()}

                        </div>


                        {/* CONVERSATION INFO */}

                        <div className="conversation-info">

                          <div className="conversation-top">

                            <strong>
                              {
                                conversationName
                              }
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
                                    hour:
                                      "2-digit",
                                    minute:
                                      "2-digit",
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

          </>

        )}

      </aside>

      {/* =====================================================
          CHAT MAIN
      ===================================================== */}

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

            {/* CHAT HEADER */}

            <div className="chat-header">

              <button
                className="back-button"
                onClick={
                  closeConversation
                }
              >
                <ArrowLeft
                  size={22}
                />
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
                      String(
                        typingUserId
                      ) !==
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
                    (previous) =>
                      !previous
                  );

                  setMessageSearch("");
                  setMessageSearchResults(
                    []
                  );
                  setMessageSearchError(
                    ""
                  );
                }}
                title="Search messages"
              >
                <Search
                  size={20}
                />
              </button>

            </div>

            {/* MESSAGE SEARCH */}

            {showMessageSearch && (
              <div className="message-search-panel">

                <div className="message-search-input">

                  <Search
                    size={18}
                  />

                  <input
                    type="text"
                    placeholder="Search messages..."
                    value={
                      messageSearch
                    }
                    onChange={
                      handleMessageSearchChange
                    }
                    autoFocus
                  />

                  {messageSearch && (
                    <button
                      onClick={() => {
                        setMessageSearch(
                          ""
                        );

                        setMessageSearchResults(
                          []
                        );

                        setMessageSearchError(
                          ""
                        );
                      }}
                    >
                      ×
                    </button>
                  )}

                </div>

                {messageSearchLoading && (
                  <div className="message-search-status">
                    Searching...
                  </div>
                )}

                {messageSearchError && (
                  <div className="message-search-error">
                    {
                      messageSearchError
                    }
                  </div>
                )}

                {!messageSearchLoading &&
                  messageSearch.trim() &&
                  !messageSearchError &&
                  messageSearchResults.length ===
                    0 && (
                    <div className="message-search-status">
                      No messages found.
                    </div>
                  )}

                {messageSearchResults.length >
                  0 && (
                  <div className="message-search-results">

                    {messageSearchResults.map(
                      (message) => (
                        <div
                          key={
                            message.id
                          }
                          className="message-search-result"
                          onClick={() =>
                            handleSearchResultClick(
                              message
                            )
                          }
                        >

                          <div className="message-search-result-user">
                            {message
                              .sender
                              ?.username ||
                              message
                                .sender
                                ?.email ||
                              "User"}
                          </div>

                          <div className="message-search-result-content">
                            {
                              message.content
                            }
                          </div>

                          <div className="message-search-result-time">
                            {message.created_at &&
                              new Date(
                                message.created_at
                              ).toLocaleString(
                                [],
                                {
                                  dateStyle:
                                    "short",
                                  timeStyle:
                                    "short",
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

            {/* MESSAGES */}

            <div
              className="messages-container"
              ref={
                messagesContainerRef
              }
              onScroll={
                handleMessagesScroll
              }
            >

              {loadingOlderMessages && (
                <div className="chat-message">
                  Loading older messages...
                </div>
              )}

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
                messages.length ===
                  0 && (
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

                    const senderId =
                      message.sender?.id ??
                      message.sender_id;

                    const isOwnMessage =
                      String(senderId) ===
                      String(user?.id);

                    return (
                      <div
                        id={`message-${message.id}`}
                        key={
                          message.id
                        }
                        className={`message-row ${
                          isOwnMessage
                            ? "own-message"
                            : "other-message"
                        }`}
                      >

                        <div className="message-bubble">

                          <div className="message-content">
                            {
                              message.content
                            }
                          </div>

                          <div className="message-meta">

                            <span>
                              {new Date(
                                message.created_at
                              ).toLocaleTimeString(
                                [],
                                {
                                  hour: "2-digit",
                                  minute:
                                    "2-digit",
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

            {/* MESSAGE INPUT */}

            <div className="message-input-area">

              <input
                type="text"
                placeholder="Type a message..."
                value={
                  messageText
                }
                onChange={
                  handleMessageInputChange
                }
                onKeyDown={
                  handleMessageKeyDown
                }
                disabled={
                  sendingMessage
                }
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
                  <Send
                    size={18}
                  />
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