import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageCircle, 
  X, 
  Minimize2, 
  Send, 
  Paperclip, 
  Mic,
  Plus,
  Search,
  MoreVertical,
  CheckCircle,
  AlertCircle,
  FileSpreadsheet,
  Presentation,
  Database,
  Play,
  Edit,
  Eye,
  Trash2
} from 'lucide-react';

interface Message {
  id: string;
  type: 'user' | 'ai' | 'system';
  content: string;
  timestamp: Date;
  buttons?: ActionButton[];
  card?: JobCard;
}

interface ActionButton {
  label: string;
  action: string;
  variant?: 'primary' | 'secondary';
}

interface JobCard {
  title: string;
  status: 'success' | 'failed' | 'running';
  lastRun: string;
  nextRun: string;
}

interface Conversation {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  isPinned?: boolean;
}

const ChatAgent: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [currentMessage, setCurrentMessage] = useState('');
  const [conversations, setConversations] = useState<Conversation[]>([
    {
      id: '1',
      title: 'Help with Excel report',
      lastMessage: 'I can help you set up an Excel job...',
      timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
      isPinned: true
    },
    {
      id: '2',
      title: 'SQL query timeout issue',
      lastMessage: 'Updated timeout to 600 seconds',
      timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000)
    },
    {
      id: '3',
      title: 'PowerPoint automation',
      lastMessage: 'Your monthly deck is ready!',
      timestamp: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000)
    }
  ]);
  const [currentConversation, setCurrentConversation] = useState<string>('1');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'ai',
      content: 'Hi! I\'m CC Assistant 👋 How can I help you today? I can:\n• Create new jobs\n• Troubleshoot errors\n• Explain features\n• Answer questions',
      timestamp: new Date(Date.now() - 10 * 60 * 1000),
      buttons: [
        { label: '📊 Create Excel Job', action: 'create_excel', variant: 'primary' },
        { label: '💾 Create SQL Job', action: 'create_sql', variant: 'secondary' },
        { label: '📈 Create PowerPoint', action: 'create_ppt', variant: 'secondary' }
      ]
    }
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [showConversations, setShowConversations] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = () => {
    if (!currentMessage.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: currentMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentMessage('');
    setIsTyping(true);

    // Simulate AI response
    setTimeout(() => {
      const aiResponse = generateAIResponse(currentMessage);
      setMessages(prev => [...prev, aiResponse]);
      setIsTyping(false);
    }, 1500);
  };

  const generateAIResponse = (userInput: string): Message => {
    const input = userInput.toLowerCase();

    // Create job responses
    if (input.includes('create') || input.includes('new job')) {
      if (input.includes('excel')) {
        return {
          id: Date.now().toString(),
          type: 'ai',
          content: 'Great! I can help you create an Excel job. Do you have a template file, or would you like to use one of our pre-built templates?',
          timestamp: new Date(),
          buttons: [
            { label: 'Upload Template', action: 'upload_template', variant: 'primary' },
            { label: 'Use Pre-built Template', action: 'use_template', variant: 'secondary' }
          ]
        };
      }
      return {
        id: Date.now().toString(),
        type: 'ai',
        content: 'I can help you create a new job! What type of job would you like to create?',
        timestamp: new Date(),
        buttons: [
          { label: '📊 Excel Report', action: 'create_excel', variant: 'primary' },
          { label: '💾 SQL Query', action: 'create_sql', variant: 'secondary' },
          { label: '📈 PowerPoint Deck', action: 'create_ppt', variant: 'secondary' }
        ]
      };
    }

    // Error/troubleshooting responses
    if (input.includes('fail') || input.includes('error') || input.includes('problem')) {
      return {
        id: Date.now().toString(),
        type: 'ai',
        content: 'Let me check your recent job failures...\n\nFound: "Daily Sales Query" failed 6 hours ago\n\n❌ Error: Query timeout (exceeded 300s)\n\n💡 Suggestions:\n• Increase timeout to 600 seconds\n• Add date filters to reduce data\n• Run during off-peak hours',
        timestamp: new Date(),
        buttons: [
          { label: 'Fix Timeout', action: 'fix_timeout', variant: 'primary' },
          { label: 'View Logs', action: 'view_logs', variant: 'secondary' }
        ]
      };
    }

    // Help/explanation responses
    if (input.includes('help') || input.includes('how') || input.includes('what')) {
      return {
        id: Date.now().toString(),
        type: 'ai',
        content: 'I\'d be happy to help! Control Center lets you automate reports and data jobs without coding. You can:\n\n✓ Create scheduled jobs (Excel, SQL, PowerPoint)\n✓ Monitor job execution and logs\n✓ Manage jobs across Dev/Semi-Prod/Prod environments\n\nWhat would you like to know more about?',
        timestamp: new Date(),
        buttons: [
          { label: 'Create My First Job', action: 'tutorial', variant: 'primary' },
          { label: 'View Documentation', action: 'docs', variant: 'secondary' }
        ]
      };
    }

    // Schedule related
    if (input.includes('schedule') || input.includes('when') || input.includes('run')) {
      return {
        id: Date.now().toString(),
        type: 'ai',
        content: 'You can schedule jobs to run:\n• Daily (specific time)\n• Weekly (specific day and time)\n• Monthly (specific day of month)\n• On-demand (manual trigger only)\n\nWhich schedule type do you need?',
        timestamp: new Date()
      };
    }

    // Default response
    return {
      id: Date.now().toString(),
      type: 'ai',
      content: 'I understand you\'re asking about: "' + userInput + '"\n\nCould you provide more details? Or would you like me to help you with one of these common tasks?',
      timestamp: new Date(),
      buttons: [
        { label: 'Create New Job', action: 'create_job', variant: 'primary' },
        { label: 'View My Jobs', action: 'view_jobs', variant: 'secondary' },
        { label: 'Get Help', action: 'help', variant: 'secondary' }
      ]
    };
  };

  const handleButtonClick = (action: string) => {
    const actionMessages: { [key: string]: string } = {
      create_excel: 'I\'d like to create an Excel job',
      create_sql: 'I\'d like to create a SQL job',
      create_ppt: 'I\'d like to create a PowerPoint job',
      upload_template: 'I\'ll upload my own template',
      use_template: 'I\'d like to use a pre-built template',
      fix_timeout: 'Please fix the timeout issue',
      view_logs: 'Show me the error logs',
      tutorial: 'Show me how to create my first job',
      docs: 'I\'d like to see the documentation',
      create_job: 'Help me create a new job',
      view_jobs: 'Show me my jobs',
      help: 'I need help'
    };

    const message = actionMessages[action] || action;
    setCurrentMessage(message);
    handleSendMessage();
  };

  const handleNewConversation = () => {
    const newConv: Conversation = {
      id: Date.now().toString(),
      title: 'New conversation',
      lastMessage: 'Started just now',
      timestamp: new Date()
    };
    setConversations(prev => [newConv, ...prev]);
    setCurrentConversation(newConv.id);
    setMessages([
      {
        id: '1',
        type: 'ai',
        content: 'Hi! I\'m CC Assistant 👋 How can I help you today?',
        timestamp: new Date(),
        buttons: [
          { label: '📊 Create Excel Job', action: 'create_excel', variant: 'primary' },
          { label: '💾 Create SQL Job', action: 'create_sql', variant: 'secondary' },
          { label: '📈 Create PowerPoint', action: 'create_ppt', variant: 'secondary' }
        ]
      }
    ]);
    setShowConversations(false);
  };

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (hours < 1) return 'Just now';
    if (hours < 24) return `${hours}h ago`;
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  };

  const formatMessageTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        style={styles.chatBubble}
        aria-label="Open chat"
      >
        <MessageCircle size={24} color="#FFFFFF" />
        <span style={styles.badge}>1</span>
      </button>
    );
  }

  return (
    <>
      {/* Backdrop */}
      <div
        style={styles.backdrop}
        onClick={() => setIsOpen(false)}
      />

      {/* Chat Sidebar */}
      <div style={{
        ...styles.chatSidebar,
        ...(isMinimized ? styles.chatSidebarMinimized : {})
      }}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.headerContent}>
            <div style={styles.headerTitle}>
              <MessageCircle size={20} color="#EB0A1E" />
              <div>
                <div style={styles.headerTitleText}>CC Assistant</div>
                <div style={styles.headerStatus}>
                  <span style={styles.statusDot}></span>
                  Online • Responds instantly
                </div>
              </div>
            </div>
            <div style={styles.headerActions}>
              <button
                onClick={() => setIsMinimized(!isMinimized)}
                style={styles.iconButton}
                aria-label="Minimize"
              >
                <Minimize2 size={18} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                style={styles.iconButton}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
          </div>
        </div>

        {!isMinimized && (
          <>
            {/* Conversations Toggle */}
            <div style={styles.conversationsToggle}>
              <button
                onClick={() => setShowConversations(!showConversations)}
                style={styles.toggleButton}
              >
                💬 Conversations ({conversations.length})
              </button>
            </div>

            {/* Conversations Panel */}
            {showConversations && (
              <div style={styles.conversationsPanel}>
                <div style={styles.conversationsHeader}>
                  <button
                    onClick={handleNewConversation}
                    style={styles.newConvButton}
                  >
                    <Plus size={16} />
                    New Conversation
                  </button>
                </div>
                <div style={styles.conversationsList}>
                  {conversations.map(conv => (
                    <div
                      key={conv.id}
                      style={{
                        ...styles.conversationItem,
                        ...(currentConversation === conv.id ? styles.conversationItemActive : {})
                      }}
                      onClick={() => {
                        setCurrentConversation(conv.id);
                        setShowConversations(false);
                      }}
                    >
                      <div style={styles.conversationTitle}>
                        {conv.isPinned && <span style={styles.pinIcon}>📌</span>}
                        {conv.title}
                      </div>
                      <div style={styles.conversationMeta}>
                        {formatTime(conv.timestamp)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Messages Area */}
            <div style={styles.messagesArea}>
              {messages.map(message => (
                <div
                  key={message.id}
                  style={{
                    ...styles.messageWrapper,
                    ...(message.type === 'user' ? styles.messageWrapperUser : {})
                  }}
                >
                  {message.type === 'ai' && (
                    <div style={styles.messageAvatar}>🤖</div>
                  )}
                  <div style={styles.messageContent}>
                    <div
                      style={{
                        ...styles.messageBubble,
                        ...(message.type === 'user' ? styles.messageBubbleUser : {})
                      }}
                    >
                      <div style={styles.messageText}>{message.content}</div>
                      {message.buttons && (
                        <div style={styles.messageButtons}>
                          {message.buttons.map((button, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleButtonClick(button.action)}
                              style={{
                                ...styles.actionButton,
                                ...(button.variant === 'primary' ? styles.actionButtonPrimary : {})
                              }}
                            >
                              {button.label}
                            </button>
                          ))}
                        </div>
                      )}
                      {message.card && (
                        <div style={styles.jobCard}>
                          <div style={styles.jobCardHeader}>
                            <FileSpreadsheet size={18} color="#EB0A1E" />
                            <span style={styles.jobCardTitle}>{message.card.title}</span>
                          </div>
                          <div style={styles.jobCardRow}>
                            <span>Status:</span>
                            <span style={{
                              ...styles.jobCardStatus,
                              ...(message.card.status === 'success' ? styles.jobCardStatusSuccess : {}),
                              ...(message.card.status === 'failed' ? styles.jobCardStatusFailed : {})
                            }}>
                              {message.card.status === 'success' && '✅ Success'}
                              {message.card.status === 'failed' && '❌ Failed'}
                              {message.card.status === 'running' && '🔄 Running'}
                            </span>
                          </div>
                          <div style={styles.jobCardRow}>
                            <span>Last run:</span>
                            <span>{message.card.lastRun}</span>
                          </div>
                          <div style={styles.jobCardRow}>
                            <span>Next run:</span>
                            <span>{message.card.nextRun}</span>
                          </div>
                          <div style={styles.jobCardActions}>
                            <button style={styles.jobCardButton}>
                              <Eye size={14} /> View
                            </button>
                            <button style={styles.jobCardButton}>
                              <Edit size={14} /> Edit
                            </button>
                            <button style={styles.jobCardButton}>
                              <Play size={14} /> Run
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                    <div style={styles.messageTime}>
                      {formatMessageTime(message.timestamp)}
                    </div>
                  </div>
                  {message.type === 'user' && (
                    <div style={styles.messageAvatar}>👤</div>
                  )}
                </div>
              ))}

              {isTyping && (
                <div style={styles.messageWrapper}>
                  <div style={styles.messageAvatar}>🤖</div>
                  <div style={styles.messageBubble}>
                    <div style={styles.typingIndicator}>
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div style={styles.inputArea}>
              <button style={styles.inputIconButton} aria-label="Attach file">
                <Paperclip size={20} />
              </button>
              <input
                type="text"
                value={currentMessage}
                onChange={(e) => setCurrentMessage(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="Type your message..."
                style={styles.input}
              />
              <button style={styles.inputIconButton} aria-label="Voice input">
                <Mic size={20} />
              </button>
              <button
                onClick={handleSendMessage}
                disabled={!currentMessage.trim()}
                style={{
                  ...styles.sendButton,
                  ...(currentMessage.trim() ? {} : styles.sendButtonDisabled)
                }}
                aria-label="Send message"
              >
                <Send size={20} />
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  chatBubble: {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    width: '60px',
    height: '60px',
    borderRadius: '50%',
    backgroundColor: '#EB0A1E',
    border: 'none',
    boxShadow: '0 4px 12px rgba(235, 10, 30, 0.4)',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.3s ease',
    zIndex: 1000,
  },
  badge: {
    position: 'absolute',
    top: '0',
    right: '0',
    backgroundColor: '#FF4444',
    color: '#FFFFFF',
    borderRadius: '50%',
    width: '20px',
    height: '20px',
    fontSize: '12px',
    fontWeight: 'bold',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  backdrop: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.3)',
    zIndex: 999,
  },
  chatSidebar: {
    position: 'fixed',
    top: 0,
    right: 0,
    width: '420px',
    height: '100vh',
    backgroundColor: '#FFFFFF',
    boxShadow: '-4px 0 20px rgba(0, 0, 0, 0.15)',
    display: 'flex',
    flexDirection: 'column',
    zIndex: 1001,
    animation: 'slideIn 0.3s ease',
  },
  chatSidebarMinimized: {
    height: 'auto',
  },
  header: {
    backgroundColor: '#FFFFFF',
    borderBottom: '1px solid #E5E5E5',
    padding: '16px',
  },
  headerContent: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  headerTitleText: {
    fontSize: '16px',
    fontWeight: 'bold',
    color: '#000000',
  },
  headerStatus: {
    fontSize: '12px',
    color: '#666666',
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    marginTop: '2px',
  },
  statusDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    backgroundColor: '#10B981',
    display: 'inline-block',
  },
  headerActions: {
    display: 'flex',
    gap: '8px',
  },
  iconButton: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: '#666666',
    padding: '4px',
    borderRadius: '4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'background-color 0.2s',
  },
  conversationsToggle: {
    padding: '12px 16px',
    borderBottom: '1px solid #E5E5E5',
  },
  toggleButton: {
    width: '100%',
    padding: '8px',
    backgroundColor: '#F5F5F5',
    border: '1px solid #DDDDDD',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: '600',
    color: '#333333',
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'background-color 0.2s',
  },
  conversationsPanel: {
    borderBottom: '1px solid #E5E5E5',
    maxHeight: '300px',
    overflowY: 'auto',
  },
  conversationsHeader: {
    padding: '12px 16px',
    borderBottom: '1px solid #E5E5E5',
  },
  newConvButton: {
    width: '100%',
    padding: '10px',
    backgroundColor: '#EB0A1E',
    color: '#FFFFFF',
    border: 'none',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    transition: 'background-color 0.2s',
  },
  conversationsList: {
    padding: '8px',
  },
  conversationItem: {
    padding: '12px',
    borderRadius: '6px',
    cursor: 'pointer',
    marginBottom: '4px',
    transition: 'background-color 0.2s',
  },
  conversationItemActive: {
    backgroundColor: '#FFF5F5',
    borderLeft: '3px solid #EB0A1E',
  },
  conversationTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#333333',
    marginBottom: '4px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  pinIcon: {
    fontSize: '12px',
  },
  conversationMeta: {
    fontSize: '12px',
    color: '#999999',
  },
  messagesArea: {
    flex: 1,
    overflowY: 'auto',
    padding: '16px',
    backgroundColor: '#F9F9F9',
  },
  messageWrapper: {
    display: 'flex',
    gap: '12px',
    marginBottom: '16px',
    alignItems: 'flex-start',
  },
  messageWrapperUser: {
    flexDirection: 'row-reverse',
  },
  messageAvatar: {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    backgroundColor: '#F0F0F0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '18px',
    flexShrink: 0,
  },
  messageContent: {
    maxWidth: '75%',
  },
  messageBubble: {
    backgroundColor: '#FFFFFF',
    padding: '12px 16px',
    borderRadius: '12px',
    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
  },
  messageBubbleUser: {
    backgroundColor: '#EB0A1E',
    color: '#FFFFFF',
  },
  messageText: {
    fontSize: '14px',
    lineHeight: '1.5',
    whiteSpace: 'pre-wrap',
  },
  messageButtons: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    marginTop: '12px',
  },
  actionButton: {
    padding: '10px 16px',
    backgroundColor: '#F5F5F5',
    color: '#333333',
    border: '1px solid #DDDDDD',
    borderRadius: '6px',
    fontSize: '13px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s',
    textAlign: 'left',
  },
  actionButtonPrimary: {
    backgroundColor: '#EB0A1E',
    color: '#FFFFFF',
    border: 'none',
  },
  jobCard: {
    marginTop: '12px',
    padding: '12px',
    backgroundColor: '#F9F9F9',
    borderRadius: '8px',
    border: '1px solid #E5E5E5',
  },
  jobCardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '12px',
  },
  jobCardTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#333333',
  },
  jobCardRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '13px',
    marginBottom: '6px',
    color: '#666666',
  },
  jobCardStatus: {
    fontWeight: '600',
  },
  jobCardStatusSuccess: {
    color: '#10B981',
  },
  jobCardStatusFailed: {
    color: '#EF4444',
  },
  jobCardActions: {
    display: 'flex',
    gap: '8px',
    marginTop: '12px',
  },
  jobCardButton: {
    flex: 1,
    padding: '6px',
    backgroundColor: '#FFFFFF',
    border: '1px solid #DDDDDD',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: '600',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '4px',
    transition: 'all 0.2s',
  },
  messageTime: {
    fontSize: '11px',
    color: '#999999',
    marginTop: '4px',
    textAlign: 'left',
  },
  typingIndicator: {
    display: 'flex',
    gap: '4px',
    padding: '4px 0',
  },
  inputArea: {
    padding: '16px',
    borderTop: '1px solid #E5E5E5',
    backgroundColor: '#FFFFFF',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  inputIconButton: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: '#666666',
    padding: '8px',
    borderRadius: '6px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'background-color 0.2s',
  },
  input: {
    flex: 1,
    padding: '12px',
    border: '2px solid #DDDDDD',
    borderRadius: '8px',
    fontSize: '14px',
    outline: 'none',
    transition: 'border-color 0.2s',
  },
  sendButton: {
    padding: '12px',
    backgroundColor: '#EB0A1E',
    color: '#FFFFFF',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'background-color 0.2s',
  },
  sendButtonDisabled: {
    backgroundColor: '#CCCCCC',
    cursor: 'not-allowed',
  },
};

// Add typing indicator animation
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(100%);
    }
    to {
      transform: translateX(0);
    }
  }

  ${styles.typingIndicator} span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    backgroundColor: #999999;
    animation: bounce 1.4s infinite ease-in-out both;
  }

  ${styles.typingIndicator} span:nth-child(1) {
    animation-delay: -0.32s;
  }

  ${styles.typingIndicator} span:nth-child(2) {
    animation-delay: -0.16s;
  }

  @keyframes bounce {
    0%, 80%, 100% {
      transform: scale(0);
    }
    40% {
      transform: scale(1);
    }
  }

  ${styles.chatBubble}:hover {
    transform: scale(1.05);
    box-shadow: 0 6px 16px rgba(235, 10, 30, 0.5);
  }

  ${styles.iconButton}:hover {
    background-color: #F5F5F5;
  }

  ${styles.toggleButton}:hover {
    background-color: #EEEEEE;
  }

  ${styles.conversationItem}:hover {
    background-color: #F5F5F5;
  }

  ${styles.actionButton}:hover {
    background-color: #EEEEEE;
    border-color: #CCCCCC;
  }

  ${styles.actionButtonPrimary}:hover {
    background-color: #C70917;
  }

  ${styles.newConvButton}:hover {
    background-color: #C70917;
  }

  ${styles.sendButton}:hover:not(:disabled) {
    background-color: #C70917;
  }

  ${styles.jobCardButton}:hover {
    background-color: #F5F5F5;
    border-color: #CCCCCC;
  }

  ${styles.inputIconButton}:hover {
    background-color: #F5F5F5;
  }

  ${styles.input}:focus {
    border-color: #EB0A1E;
  }
`;
document.head.appendChild(styleSheet);

export default ChatAgent;
